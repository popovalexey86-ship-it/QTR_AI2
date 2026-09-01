from datetime import datetime

from core.analysis_context import AnalysisContext
from core.candle import Candle
from core.market_data import MarketData
from core.setup import Setup
from core.trend import Trend
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


def test_bullish_setup_is_forwarded_when_long_smc_gate_accepts_it():
    market_data = make_market_data()
    context = AnalysisContext(market_data=market_data)
    context.trend = Trend.BULLISH
    context.setup = make_setup(Trend.BULLISH)

    result = QTRLongStrategy(
        FakeAnalysisEngine(context),
        setup_detector=AcceptingLongSetupDetector(),
    ).analyze(market_data)

    assert result.setup is not None
    assert result.setup.trend == Trend.BULLISH


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
