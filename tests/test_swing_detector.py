from datetime import datetime, timedelta

from core.candle import Candle
from core.market_data import MarketData
from core.swing_type import SwingType
from market_structure.swing_detector import SwingDetector


def create_market_data():
    start = datetime(2025, 1, 1)

    highs = [10, 12, 15, 12, 10]
    lows = [5, 6, 7, 6, 5]

    candles = []

    for i in range(len(highs)):
        candles.append(
            Candle(
                timestamp=start + timedelta(minutes=i),
                open=8,
                high=highs[i],
                low=lows[i],
                close=8,
                volume=100,
            )
        )

    return MarketData(
        symbol="BTCUSDT",
        timeframe="M5",
        candles=candles,
    )


def create_market_data_low():
    start = datetime(2025, 1, 1)

    highs = [10, 11, 12, 11, 10]
    lows = [5, 4, 2, 4, 5]

    candles = []

    for i in range(len(highs)):
        candles.append(
            Candle(
                timestamp=start + timedelta(minutes=i),
                open=8,
                high=highs[i],
                low=lows[i],
                close=8,
                volume=100,
            )
        )

    return MarketData(
        symbol="BTCUSDT",
        timeframe="M5",
        candles=candles,
    )


def test_detect_single_swing_high():
    market = create_market_data()

    detector = SwingDetector()

    swings = detector.detect(market)

    highs = [s for s in swings if s.type == SwingType.HIGH]

    assert len(highs) == 1
    assert highs[0].index == 2
    assert highs[0].price == 15


def test_detect_single_swing_low():
    market = create_market_data_low()

    detector = SwingDetector()

    swings = detector.detect(market)

    lows = [s for s in swings if s.type == SwingType.LOW]

    assert len(lows) == 1
    assert lows[0].index == 2
    assert lows[0].price == 2