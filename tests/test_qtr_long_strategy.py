from datetime import datetime

from core.analysis_context import AnalysisContext
from core.candle import Candle
from core.liquidity_sweep import LiquiditySweep, LiquiditySweepDirection
from core.market_data import MarketData
from core.order_block import OrderBlock, OrderBlockDirection
from core.setup import Setup
from core.trend import Trend
from strategies.qtr_long.score import LongScore
from strategies.qtr_long.setup import LongSetupCandidate, LongSetupType
from strategies.qtr_long.strategy import QTRLongStrategy


def make_market_data() -> MarketData:
    return MarketData(
        symbol="BTCUSDT",
        timeframe="15",
        candles=[
            Candle(
                index=1,
                timestamp=datetime(2025, 1, 1),
                open=100,
                high=101,
                low=99,
                close=100,
                volume=1,
            )
        ],
    )


def make_setup(trend: Trend) -> Setup:
    return Setup(
        index=1,
        timestamp=datetime(2025, 1, 1),
        trend=trend,
        entry=100,
        stop_loss=98 if trend == Trend.BULLISH else 102,
    )


def make_candidate() -> LongSetupCandidate:
    timestamp = datetime(2025, 1, 1)
    return LongSetupCandidate(
        type=LongSetupType.SWEEP_RECLAIM_ORDER_BLOCK,
        liquidity_sweep=LiquiditySweep(
            index=1,
            timestamp=timestamp,
            direction=LiquiditySweepDirection.BULLISH,
            swept_price=99.0,
            extreme_price=98.0,
            reclaim_close=100.0,
        ),
        order_block=OrderBlock(
            index=1,
            timestamp=timestamp,
            direction=OrderBlockDirection.BULLISH,
            low=98.5,
            high=100.0,
        ),
        entry=100.0,
        stop_loss=98.0,
    )


class FakeAnalysisEngine:
    def __init__(self, context: AnalysisContext):
        self.context = context

    def analyze(self, market_data: MarketData) -> AnalysisContext:
        assert market_data is self.context.market_data
        return self.context


class AcceptingLongSetupDetector:
    def detect(self, context: AnalysisContext) -> LongSetupCandidate:
        return make_candidate()


class FixedScoringEngine:
    def __init__(self, total: int):
        self.total = total

    def score(self, context: AnalysisContext, candidate: LongSetupCandidate) -> LongScore:
        assert candidate.entry == 100
        if self.total >= 80:
            return LongScore(20, 20, 15, 10, 5, 5, 5)  # 80
        return LongScore(15, 15, 10, 5, 5, 10, 5)  # 65


def test_bullish_setup_is_forwarded_when_smc_score_and_risk_gates_accept_it():
    market_data = make_market_data()
    context = AnalysisContext(market_data=market_data)
    context.trend = Trend.BULLISH
    context.setup = make_setup(Trend.BULLISH)

    strategy = QTRLongStrategy(
        FakeAnalysisEngine(context),
        setup_detector=AcceptingLongSetupDetector(),
        scoring_engine=FixedScoringEngine(80),
    )
    result = strategy.analyze(market_data)

    assert result.setup is not None
    assert result.setup.trend == Trend.BULLISH
    assert result.setup.entry == 100
    assert result.setup.stop_loss == 98
    assert strategy.last_score is not None
    assert strategy.last_score.total == 80
    assert strategy.last_risk_plan is not None


def test_bullish_setup_is_removed_when_score_is_below_threshold():
    market_data = make_market_data()
    context = AnalysisContext(market_data=market_data)
    context.trend = Trend.BULLISH
    context.setup = make_setup(Trend.BULLISH)

    strategy = QTRLongStrategy(
        FakeAnalysisEngine(context),
        setup_detector=AcceptingLongSetupDetector(),
        scoring_engine=FixedScoringEngine(65),
    )
    result = strategy.analyze(market_data)

    assert result.setup is None
    assert strategy.last_score is not None
    assert strategy.last_score.total == 65
    assert strategy.last_risk_plan is None


def test_minimum_score_is_configurable():
    market_data = make_market_data()
    context = AnalysisContext(market_data=market_data)
    context.trend = Trend.BULLISH
    context.setup = make_setup(Trend.BULLISH)

    result = QTRLongStrategy(
        FakeAnalysisEngine(context),
        setup_detector=AcceptingLongSetupDetector(),
        scoring_engine=FixedScoringEngine(65),
        minimum_score=60,
    ).analyze(market_data)

    assert result.setup is not None


def test_range_can_build_its_own_bullish_setup_from_valid_candidate():
    market_data = make_market_data()
    context = AnalysisContext(market_data=market_data)
    context.trend = Trend.RANGE
    context.setup = None

    result = QTRLongStrategy(
        FakeAnalysisEngine(context),
        setup_detector=AcceptingLongSetupDetector(),
        scoring_engine=FixedScoringEngine(80),
    ).analyze(market_data)

    assert result.setup is not None
    assert result.setup.trend == Trend.BULLISH
    assert result.setup.entry == 100
    assert result.setup.stop_loss == 98


def test_bullish_setup_is_removed_without_long_smc_confirmation():
    market_data = make_market_data()
    context = AnalysisContext(market_data=market_data)
    context.trend = Trend.BULLISH
    context.setup = make_setup(Trend.BULLISH)

    result = QTRLongStrategy(FakeAnalysisEngine(context)).analyze(market_data)

    assert result.setup is None


def test_bearish_market_blocks_setup():
    market_data = make_market_data()
    context = AnalysisContext(market_data=market_data)
    context.trend = Trend.BEARISH
    context.setup = make_setup(Trend.BEARISH)

    result = QTRLongStrategy(FakeAnalysisEngine(context)).analyze(market_data)

    assert result.setup is None


def test_bearish_setup_cannot_leak_through_range_context():
    market_data = make_market_data()
    context = AnalysisContext(market_data=market_data)
    context.trend = Trend.RANGE
    context.setup = make_setup(Trend.BEARISH)

    result = QTRLongStrategy(FakeAnalysisEngine(context)).analyze(market_data)

    assert result.setup is None
