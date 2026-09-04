from datetime import datetime

from core.candle import Candle
from core.fair_value_gap import FairValueGapDirection, FairValueGapStatus
from core.fair_value_gap_engine import FairValueGapEngine
from core.market_data import MarketData


def candle(index, open_, high, low, close):
    return Candle(datetime(2025, 1, 1), open_, high, low, close, 1, index=index)


def test_detects_bullish_three_candle_fvg():
    data = MarketData("BTCUSDT", "15", [
        candle(0, 100, 101, 99, 100),
        candle(1, 100, 108, 100, 107),
        candle(2, 107, 110, 103, 109),
    ])

    gap = FairValueGapEngine().detect(data)

    assert gap is not None
    assert gap.direction == FairValueGapDirection.BULLISH
    assert gap.low == 101
    assert gap.high == 103


def test_no_fvg_when_first_and_third_candles_overlap():
    data = MarketData("BTCUSDT", "15", [
        candle(0, 100, 103, 99, 102),
        candle(1, 102, 106, 101, 105),
        candle(2, 105, 107, 102, 106),
    ])
    assert FairValueGapEngine().detect(data) is None


def test_bullish_fvg_mitigates_then_fills():
    engine = FairValueGapEngine()
    data = MarketData("BTCUSDT", "15", [
        candle(0, 100, 101, 99, 100),
        candle(1, 100, 108, 100, 107),
        candle(2, 107, 110, 103, 109),
    ])
    gap = engine.detect(data)
    assert gap is not None

    mitigated = engine.update_status(gap, candle(3, 105, 106, 102, 104))
    assert mitigated.status == FairValueGapStatus.MITIGATED

    filled = engine.update_status(mitigated, candle(4, 103, 104, 100, 102))
    assert filled.status == FairValueGapStatus.FILLED
