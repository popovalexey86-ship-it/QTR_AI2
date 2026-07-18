from datetime import datetime

from core.bos import BOS
from core.bos_type import BOSType
from core.market_structure_state import MarketStructureState
from core.setup import Setup
from core.setup_engine import SetupEngine
from core.trend import Trend


def make_bos(index: int, bos_type: BOSType) -> BOS:
    return BOS(
        index=index,
        timestamp=datetime(2025, 1, 1),
        price=100,
        type=bos_type,
    )


def test_no_setup_when_range():

    state = MarketStructureState()

    state.trend = Trend.RANGE

    engine = SetupEngine()

    assert engine.detect(state) is None


def test_detect_bullish_setup():

    state = MarketStructureState()

    state.trend = Trend.BULLISH
    state.last_bos = make_bos(10, BOSType.BULLISH)

    engine = SetupEngine()

    setup = engine.detect(state)

    assert setup is not None
    assert isinstance(setup, Setup)

    assert setup.index == 10
    assert setup.timestamp == datetime(2025, 1, 1)
    assert setup.trend == Trend.BULLISH
    assert setup.entry == 100
    assert setup.stop_loss == 100


def test_detect_bearish_setup():

    state = MarketStructureState()

    state.trend = Trend.BEARISH
    state.last_bos = make_bos(20, BOSType.BEARISH)

    engine = SetupEngine()

    setup = engine.detect(state)

    assert setup is not None
    assert isinstance(setup, Setup)

    assert setup.index == 20
    assert setup.timestamp == datetime(2025, 1, 1)
    assert setup.trend == Trend.BEARISH
    assert setup.entry == 100
    assert setup.stop_loss == 100
