from datetime import datetime

from core.logger import logger

from core.decision import Decision
from core.exceptions import DuplicatePendingSetupError
from core.market_data import MarketData
from core.execution import Execution
from core.risk_manager import RiskManager
from core.decision_engine import DecisionEngine
from core.position_monitor import PositionMonitor
from core.pending_entry import (
    PendingEntry,
    build_order_link_id,
    build_setup_key,
)
from core.notification import NotificationError, NotificationPort
from strategies.strategy import Strategy


class TradingEngine:
    """
    Центральный торговый движок.

    Координирует:
    - анализ рынка;
    - принятие решения;
    - риск-менеджмент;
    - исполнение ордеров.
    """

    def __init__(
        self,
        strategy: Strategy,
        decision_engine: DecisionEngine,
        risk_manager: RiskManager,
        execution: Execution,
        position_monitor: PositionMonitor,
        notifier: NotificationPort | None = None,
    ):
        self._strategy = strategy
        self._decision_engine = decision_engine
        self._risk_manager = risk_manager
        self._execution = execution
        self._position_monitor = position_monitor
        self._notifier = notifier

    def recover_runtime_state(self) -> PendingEntry | None:
        pending = self._execution.recover_pending_entry()
        self._position_monitor.update()
        self._deliver_pending_entry_events()
        return pending

    def poll_runtime_state(self) -> PendingEntry | None:
        pending = self._execution.refresh_pending_entry()
        self._position_monitor.update()
        self._deliver_pending_entry_events()
        return pending

    def age_pending_entry(
        self,
        completed_candle_timestamps: tuple[datetime, ...],
        *,
        ttl_candles: int,
    ) -> PendingEntry | None:
        pending = self._execution.age_pending_entry(
            completed_candle_timestamps,
            ttl_candles=ttl_candles,
        )
        self._deliver_pending_entry_events()
        return pending

    def _deliver_pending_entry_events(self) -> None:
        events = self._execution.drain_pending_entry_events()
        if self._notifier is None:
            return
        for event in events:
            try:
                self._notifier.pending_entry_event(event)
            except NotificationError as error:
                logger.error(
                    "Pending-entry notification failed. "
                    "OrderLinkId=%s Error=%s",
                    event.order_link_id,
                    type(error).__name__,
                )

    def process(
        self,
        market_data: MarketData,
    ) -> None:

        logger.info("Trading cycle started.")
        self._position_monitor.update()
        signal_timestamp = market_data.last.timestamp
        current_market_price = market_data.last.close

        if self._position_monitor.has_open_position():
            _log_setup_evaluation(
                outcome="rejected",
                reason="open_position_exists",
                setup_timestamp=None,
                signal_timestamp=signal_timestamp,
                setup_id=None,
                setup_key=None,
                calculated_entry=None,
                current_market_price=current_market_price,
            )
            logger.info("Open position already exists. Skipping trade.")
            return

        if self._execution.has_pending_entry():
            _log_setup_evaluation(
                outcome="rejected",
                reason="pending_entry_exists",
                setup_timestamp=None,
                signal_timestamp=signal_timestamp,
                setup_id=None,
                setup_key=None,
                calculated_entry=None,
                current_market_price=current_market_price,
            )
            logger.info("Pending entry already exists. Skipping trade.")
            return

        # Обновляем состояние открытой позиции
        # Анализируем рынок
        context = self._strategy.analyze(
            market_data,
        )

        if context.setup is None:
            _log_setup_evaluation(
                outcome="rejected",
                reason="setup_not_found",
                setup_timestamp=None,
                signal_timestamp=signal_timestamp,
                setup_id=None,
                setup_key=None,
                calculated_entry=None,
                current_market_price=current_market_price,
            )
            logger.info("Setup not found.")
            return

        logger.info("Setup found.")

        # Принимаем решение
        decision = self._decision_engine.decide(
            context.setup,
        )

        logger.info(f"Decision: {decision.name}")

        if decision == Decision.SKIP:
            _log_setup_evaluation(
                outcome="rejected",
                reason="decision_skip",
                setup_timestamp=context.setup.timestamp,
                signal_timestamp=signal_timestamp,
                setup_id=None,
                setup_key=None,
                calculated_entry=context.setup.entry,
                current_market_price=current_market_price,
            )
            logger.info("Trade skipped.")
            return

        # Не открываем вторую позицию
        # Формируем заявку
        request = self._risk_manager.build(
            context.setup,
            decision,
        )
        setup_key = build_setup_key(
            symbol=market_data.symbol,
            direction=request.decision,
            setup_timestamp=context.setup.timestamp,
            entry=request.entry,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
        )
        setup_id = build_order_link_id(setup_key)

        logger.info("Submitting pending entry to broker.")

        # Исполняем заявку
        try:
            pending = self._execution.submit_pending_entry(
                request,
                setup_timestamp=context.setup.timestamp,
                signal_timestamp=signal_timestamp,
                authoritative_symbol=market_data.symbol,
            )
        except DuplicatePendingSetupError:
            _log_setup_evaluation(
                outcome="rejected",
                reason="duplicate_setup",
                setup_timestamp=context.setup.timestamp,
                signal_timestamp=signal_timestamp,
                setup_id=setup_id,
                setup_key=setup_key,
                calculated_entry=request.entry,
                current_market_price=current_market_price,
            )
            logger.info("Duplicate setup suppressed.")
            return

        _log_setup_evaluation(
            outcome="accepted",
            reason="pending_entry_submitted",
            setup_timestamp=context.setup.timestamp,
            signal_timestamp=signal_timestamp,
            setup_id=pending.order_link_id,
            setup_key=pending.setup_key,
            calculated_entry=request.entry,
            current_market_price=current_market_price,
        )
        logger.info(
            "Pending entry submitted. OrderLinkId=%s ExchangeOrderId=%s "
            "SetupTimestamp=%s SignalTimestamp=%s Entry=%s MarketPrice=%s",
            pending.order_link_id,
            pending.exchange_order_id,
            context.setup.timestamp.isoformat(),
            signal_timestamp.isoformat(),
            request.entry,
            current_market_price,
        )
        self._deliver_pending_entry_events()

        logger.info("Trading cycle completed.")


def _log_setup_evaluation(
    *,
    outcome: str,
    reason: str,
    setup_timestamp: datetime | None,
    signal_timestamp: datetime,
    setup_id: str | None,
    setup_key: str | None,
    calculated_entry: float | None,
    current_market_price: float,
) -> None:
    logger.info(
        "Setup evaluation | outcome=%s reason=%s setup_timestamp=%s "
        "signal_timestamp=%s setup_id=%s setup_key=%s "
        "calculated_entry=%s current_market_price=%s",
        outcome,
        reason,
        None if setup_timestamp is None else setup_timestamp.isoformat(),
        signal_timestamp.isoformat(),
        setup_id,
        setup_key,
        calculated_entry,
        current_market_price,
    )
