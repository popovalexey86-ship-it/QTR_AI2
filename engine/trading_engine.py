from core.logger import logger

from core.decision import Decision
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
        if self._position_monitor.has_open_position():
            logger.info(
                "Open position already exists. Skipping trade."
            )
            return

        # Формируем заявку
        request = self._risk_manager.build(
            context.setup,
            decision,
        )

        logger.info("Sending order to broker.")

        # Исполняем заявку
        position = self._execution.execute(
            request,
        )

        logger.info(
            f"Position opened successfully. Ticket={position.ticket}"
        )

        logger.info("Trading cycle completed.")
