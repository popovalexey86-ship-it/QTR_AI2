from core.analysis_context import AnalysisContext
from core.analysis_engine import AnalysisEngine
from core.market_data import MarketData
from core.trend import Trend
from strategies.qtr_long.regime import LongMarketRegime, LongRegimeEngine
from strategies.strategy import Strategy


class QTRLongStrategy(Strategy):
    """Long-only strategy adapter around the shared market analysis pipeline.

    Shared analysis is allowed to observe bullish, bearish, and ranging market
    structure. QTR Long converts that information into one question only:
    should a BUY setup be allowed to continue?
    """

    def __init__(
        self,
        analysis_engine: AnalysisEngine,
        regime_engine: LongRegimeEngine | None = None,
    ):
        self._analysis_engine = analysis_engine
        self._regime_engine = regime_engine or LongRegimeEngine()

    def analyze(self, market_data: MarketData) -> AnalysisContext:
        context = self._analysis_engine.analyze(market_data)
        regime = self._regime_engine.evaluate(context)

        if regime == LongMarketRegime.BLOCKED:
            context.setup = None
            return context

        # Hard strategy-level invariant: QTR Long never forwards a bearish or
        # non-directional setup to the decision/risk/execution pipeline.
        if context.setup is not None and context.setup.trend != Trend.BULLISH:
            context.setup = None

        return context
