from core.logger import logger

from core.decision import Decision
from core.exceptions import DuplicatePendingSetupError
from core.market_data import MarketData
from core.execution import Execution
from core.risk_manager import RiskManager
from core.decision_engine import DecisionEngine
from core.position_monitor import PositionMonitor
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
    ):
        self._strategy = strategy
        self._decision_engine = decision_engine
        self._risk_manager = risk_manager
        self._execution = execution
        self._position_monitor = position_monitor

    def process(
        self,
        market_data: MarketData,
    ) -> None:

        logger.info("Trading cycle started.")
        self._position_monitor.update()

        if self._position_monitor.has_open_position():
            logger.info("Open position already exists. Skipping trade.")
            return

        if self._execution.has_pending_entry():
            logger.info("Pending entry already exists. Skipping trade.")
            return

        # Обновляем состояние открытой позиции
        # Анализируем рынок
        context = self._strategy.analyze(
            market_data,
        )

        if context.setup is None:
            logger.info("Setup not found.")
            return

        logger.info("Setup found.")

        # Принимаем решение
        decision = self._decision_engine.decide(
            context.setup,
        )

        logger.info(f"Decision: {decision.name}")

        if decision == Decision.SKIP:
            logger.info("Trade skipped.")
            return

        # Не открываем вторую позицию
        # Формируем заявку
        request = self._risk_manager.build(
            context.setup,
            decision,
        )

        logger.info("Submitting pending entry to broker.")

        # Исполняем заявку
        try:
            pending = self._execution.submit_pending_entry(
                request,
                setup_timestamp=context.setup.timestamp,
                signal_timestamp=market_data.last.timestamp,
                authoritative_symbol=market_data.symbol,
            )
        except DuplicatePendingSetupError:
            logger.info("Duplicate setup suppressed.")
            return

        logger.info(
            "Pending entry submitted. OrderLinkId=%s ExchangeOrderId=%s",
            pending.order_link_id,
            pending.exchange_order_id,
        )

        logger.info("Trading cycle completed.")
