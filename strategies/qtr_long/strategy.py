from core.analysis_context import AnalysisContext
from core.analysis_engine import AnalysisEngine
from core.market_data import MarketData
from core.trend import Trend
from strategies.qtr_long.regime import LongMarketRegime, LongRegimeEngine
from strategies.qtr_long.score import LongScore
from strategies.qtr_long.scoring import LongScoringEngine
from strategies.qtr_long.setup import LongSetupCandidate
from strategies.qtr_long.setup_detector import LongSetupDetector
from strategies.strategy import Strategy


class QTRLongStrategy(Strategy):
    """Long-only strategy adapter around the shared market analysis pipeline.

    QTR Long has only two valid outcomes for a new opportunity: allow a BUY
    candidate to continue, or SKIP it. Bearish information can block a long,
    but it can never be converted into a short entry by this strategy.
    """

    def __init__(
        self,
        analysis_engine: AnalysisEngine,
        regime_engine: LongRegimeEngine | None = None,
        setup_detector: LongSetupDetector | None = None,
        scoring_engine: LongScoringEngine | None = None,
        minimum_score: int = 80,
    ):
        if not 0 <= minimum_score <= 100:
            raise ValueError("minimum_score must be between 0 and 100")

        self._analysis_engine = analysis_engine
        self._regime_engine = regime_engine or LongRegimeEngine()
        self._setup_detector = setup_detector or LongSetupDetector()
        self._scoring_engine = scoring_engine or LongScoringEngine()
        self._minimum_score = minimum_score
        self._last_candidate: LongSetupCandidate | None = None
        self._last_score: LongScore | None = None

    @property
    def last_candidate(self) -> LongSetupCandidate | None:
        return self._last_candidate

    @property
    def last_score(self) -> LongScore | None:
        return self._last_score

    def analyze(self, market_data: MarketData) -> AnalysisContext:
        context = self._analysis_engine.analyze(market_data)
        self._last_candidate = None
        self._last_score = None
        regime = self._regime_engine.evaluate(context)

        if regime == LongMarketRegime.BLOCKED:
            context.setup = None
            return context

        # Hard strategy-level invariant: QTR Long never forwards a bearish or
        # non-directional setup to the decision/risk/execution pipeline.
        if context.setup is not None and context.setup.trend != Trend.BULLISH:
            context.setup = None
            return context

        candidate = self._setup_detector.detect(context)
        if candidate is None:
            context.setup = None
            return context

        self._last_candidate = candidate
        self._last_score = self._scoring_engine.score(context, candidate)

        if self._last_score.total < self._minimum_score:
            context.setup = None

        return context
