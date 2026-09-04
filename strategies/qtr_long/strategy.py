from core.analysis_context import AnalysisContext
from core.analysis_engine import AnalysisEngine
from core.market_data import MarketData
from core.setup import Setup
from core.trend import Trend
from strategies.qtr_long.regime import LongMarketRegime, LongRegimeEngine
from strategies.qtr_long.risk import LongRiskGate, LongRiskPlan
from strategies.qtr_long.score import LongScore
from strategies.qtr_long.scoring import LongScoringEngine
from strategies.qtr_long.setup import LongSetupCandidate
from strategies.qtr_long.setup_detector import LongSetupDetector
from strategies.strategy import Strategy


class QTRLongStrategy(Strategy):
    """Long-only strategy adapter around the shared market analysis pipeline."""

    def __init__(
        self,
        analysis_engine: AnalysisEngine,
        regime_engine: LongRegimeEngine | None = None,
        setup_detector: LongSetupDetector | None = None,
        scoring_engine: LongScoringEngine | None = None,
        risk_gate: LongRiskGate | None = None,
        minimum_score: int = 80,
    ):
        if not 0 <= minimum_score <= 100:
            raise ValueError("minimum_score must be between 0 and 100")

        self._analysis_engine = analysis_engine
        self._regime_engine = regime_engine or LongRegimeEngine()
        self._setup_detector = setup_detector or LongSetupDetector()
        self._scoring_engine = scoring_engine or LongScoringEngine()
        self._risk_gate = risk_gate or LongRiskGate(minimum_score=minimum_score)
        self._last_candidate: LongSetupCandidate | None = None
        self._last_score: LongScore | None = None
        self._last_risk_plan: LongRiskPlan | None = None

    @property
    def last_candidate(self) -> LongSetupCandidate | None:
        return self._last_candidate

    @property
    def last_score(self) -> LongScore | None:
        return self._last_score

    @property
    def last_risk_plan(self) -> LongRiskPlan | None:
        return self._last_risk_plan

    def analyze(self, market_data: MarketData) -> AnalysisContext:
        context = self._analysis_engine.analyze(market_data)
        self._last_candidate = None
        self._last_score = None
        self._last_risk_plan = None

        regime = self._regime_engine.evaluate(context)
        if regime == LongMarketRegime.BLOCKED:
            context.setup = None
            return context

        if context.setup is not None and context.setup.trend != Trend.BULLISH:
            context.setup = None

        candidate = self._setup_detector.detect(context)
        if candidate is None:
            context.setup = None
            return context

        self._last_candidate = candidate
        self._last_score = self._scoring_engine.score(context, candidate)
        self._last_risk_plan = self._risk_gate.evaluate(candidate, self._last_score)

        if self._last_risk_plan is None:
            context.setup = None
            return context

        # QTR Long owns its final BUY setup. This deliberately avoids relying
        # on the generic SetupEngine, which can suppress RANGE contexts even
        # when a valid range-low liquidity sweep/reclaim exists.
        context.setup = Setup(
            index=context.market_data.last.index,
            timestamp=context.market_data.last.timestamp,
            trend=Trend.BULLISH,
            entry=self._last_risk_plan.entry,
            stop_loss=self._last_risk_plan.stop_loss,
        )
        return context
