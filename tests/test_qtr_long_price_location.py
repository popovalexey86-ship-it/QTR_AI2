from datetime import datetime

from core.candle import Candle
from core.market_data import MarketData
from strategies.qtr_long.price_location import PriceLocationEngine, PriceZone


def data_with_close(close: float) -> MarketData:
    return MarketData("BTCUSDT", "15", [
        Candle(datetime(2025, 1, 1), 100, 110, 90, 100, 1, index=0),
        Candle(datetime(2025, 1, 2), 100, 109, 91, close, 1, index=1),
    ])


def test_discount_zone():
    location = PriceLocationEngine().evaluate(data_with_close(96))
    assert location is not None
    assert location.zone == PriceZone.DISCOUNT


def test_equilibrium_zone():
    location = PriceLocationEngine().evaluate(data_with_close(100))
    assert location is not None
    assert location.zone == PriceZone.EQUILIBRIUM


def test_premium_zone():
    location = PriceLocationEngine().evaluate(data_with_close(106))
    assert location is not None
    assert location.zone == PriceZone.PREMIUM
