from datetime import datetime

from core.analysis_context import AnalysisContext
from core.candle import Candle
from core.market_data import MarketData
from core.setup import Setup
from core.trend import Trend
from strategies.qtr_long.score import LongScore
from strategies.qtr_long.strategy import QTRLongStrategy


def make_market_data() -> MarketData:
    return MarketData(
        symbol="BTCUSDT",
        timeframe="15",
        candles=[
            Candle(
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
        stop_loss=95 if trend == Trend.BULLISH else 105,
    )


class FakeAnalysisEngine:
    def __init__(self, context: AnalysisContext):
        self.context = context

    def analyze(self, market_data: MarketData) -> AnalysisContext:
        assert market_data is self.context.market_data
        return self.context


class AcceptingLongSetupDetector:
    def detect(self, context: AnalysisContext):
        assert context.setup is not None
        return object()


class FixedScoringEngine:
    def __init__(self, total: int):
        self.total = total

    def score(self, context: AnalysisContext, candidate) -> LongScore:
        assert context.setup is not None
        assert candidate is not None
        if self.total >= 80:
            return LongScore(20, 20, 15, 10, 5, 5, 5)  # 80
        return LongScore(15, 15, 10, 5, 5, 10, 5)  # 65


def test_bullish_setup_is_forwarded_when_smc_and_score_gates_accept_it():
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
    assert strategy.last_score is not None
    assert strategy.last_score.total == 80


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


def test_bearish_setup_is_removed_even_outside_bearish_regime():
    market_data = make_market_data()
    context = AnalysisContext(market_data=market_data)
    context.trend = Trend.RANGE
    context.setup = make_setup(Trend.BEARISH)

    result = QTRLongStrategy(FakeAnalysisEngine(context)).analyze(market_data)

    assert result.setup is None


def test_range_without_setup_remains_valid_analysis_context():
    market_data = make_market_data()
    context = AnalysisContext(market_data=market_data)
    context.trend = Trend.RANGE

    result = QTRLongStrategy(FakeAnalysisEngine(context)).analyze(market_data)

    assert result is context
    assert result.setup is None
