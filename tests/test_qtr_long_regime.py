from datetime import datetime

from core.analysis_context import AnalysisContext
from core.candle import Candle
from core.market_data import MarketData
from core.trend import Trend
from strategies.qtr_long.regime import LongMarketRegime, LongRegimeEngine


def make_context(trend: Trend | None) -> AnalysisContext:
    market_data = MarketData(
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
    context = AnalysisContext(market_data=market_data)
    context.trend = trend
    return context


def test_bullish_regime_allows_long_search():
    assert LongRegimeEngine().evaluate(make_context(Trend.BULLISH)) == LongMarketRegime.ALLOWED


def test_bearish_regime_blocks_long_search():
    assert LongRegimeEngine().evaluate(make_context(Trend.BEARISH)) == LongMarketRegime.BLOCKED


def test_range_is_conditional_not_automatically_blocked():
    assert LongRegimeEngine().evaluate(make_context(Trend.RANGE)) == LongMarketRegime.CONDITIONAL


def test_unknown_trend_is_conditional():
    assert LongRegimeEngine().evaluate(make_context(None)) == LongMarketRegime.CONDITIONAL
