from core.analysis_context import AnalysisContext
from core.analysis_engine import AnalysisEngine
from core.market_data import MarketData

from strategies.strategy import Strategy


class SMCStrategy(Strategy):
    """
    SMC-стратегия.
    Выполняет только анализ рынка и возвращает AnalysisContext.
    """

    def __init__(
        self,
        analysis_engine: AnalysisEngine,
    ):
        self._analysis_engine = analysis_engine

    def analyze(
        self,
        market_data: MarketData,
    ) -> AnalysisContext:
        return self._analysis_engine.analyze(
            market_data,
        )