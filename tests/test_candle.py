from datetime import datetime

from core.candle import Candle


def test_create_candle():

    candle = Candle(
        timestamp=datetime(2025, 7, 16, 12, 0),
        open=100.0,
        high=110.0,
        low=95.0,
        close=105.0,
        volume=2500.0,
    )

    assert candle.open == 100.0
    assert candle.high == 110.0
    assert candle.low == 95.0
    assert candle.close == 105.0
    assert candle.volume == 2500.0
    import pytest


def test_candle_is_immutable():

    candle = Candle(
        timestamp=datetime.now(),
        open=1,
        high=2,
        low=0.5,
        close=1.5,
        volume=100,
    )

    with pytest.raises(AttributeError):
        candle.close = 10
