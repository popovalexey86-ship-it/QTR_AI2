from datetime import datetime

from core.setup import Setup
from core.trend import Trend


def test_create_setup():

    setup = Setup(
        index=10,
        timestamp=datetime(2025, 1, 1),
        trend=Trend.BULLISH,
        entry=100.0,
        stop_loss=95.0,
    )

    assert setup.index == 10
    assert setup.timestamp == datetime(2025, 1, 1)
    assert setup.trend == Trend.BULLISH
    assert setup.entry == 100.0
    assert setup.stop_loss == 95.0


def test_setup_is_immutable():

    setup = Setup(
        index=10,
        timestamp=datetime(2025, 1, 1),
        trend=Trend.BULLISH,
        entry=100.0,
        stop_loss=95.0,
    )

    try:
        setup.entry = 101.0
        assert False
    except AttributeError:
        assert True
