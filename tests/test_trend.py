from core.trend import Trend


def test_trend_values():

    assert Trend.BULLISH.value == "BULLISH"
    assert Trend.BEARISH.value == "BEARISH"
    assert Trend.RANGE.value == "RANGE"


def test_trend_comparison():

    trend = Trend.BULLISH

    assert trend == Trend.BULLISH
    assert trend != Trend.BEARISH
    assert trend != Trend.RANGE