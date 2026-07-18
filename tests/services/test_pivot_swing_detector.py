from core.swing_type import SwingType

from services.pivot_swing_detector import PivotSwingDetector

from tests.builders.candle_builder import CandleBuilder
from tests.builders.market_data_builder import MarketDataBuilder


def test_detect_single_swing_high():
    market_data = (
        MarketDataBuilder()
        .add_candle(CandleBuilder().high(10).low(5).build())
        .add_candle(CandleBuilder().high(12).low(6).build())
        .add_candle(CandleBuilder().high(15).low(7).build())
        .add_candle(CandleBuilder().high(11).low(6).build())
        .add_candle(CandleBuilder().high(9).low(5).build())
        .build()
    )

    detector = PivotSwingDetector()

    swings = detector.detect(market_data)

    assert len(swings) == 1

    swing = swings[0]

    assert swing.index == 2
    assert swing.price == 15
    assert swing.type == SwingType.HIGH


def test_detect_single_swing_low():
    market_data = (
        MarketDataBuilder()
        .add_candle(CandleBuilder().high(15).low(8).build())
        .add_candle(CandleBuilder().high(14).low(6).build())
        .add_candle(CandleBuilder().high(13).low(3).build())
        .add_candle(CandleBuilder().high(14).low(5).build())
        .add_candle(CandleBuilder().high(15).low(7).build())
        .build()
    )

    detector = PivotSwingDetector()

    swings = detector.detect(market_data)

    assert len(swings) == 1

    swing = swings[0]

    assert swing.index == 2
    assert swing.price == 3
    assert swing.type == SwingType.LOW
