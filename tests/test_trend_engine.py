from datetime import datetime

from core.bos import BOS
from core.bos_type import BOSType
from core.choch import CHOCH
from core.choch_type import CHOCHType
from core.market_structure_state import MarketStructureState
from core.trend import Trend
from core.trend_engine import TrendEngine


def make_bos(index: int, bos_type: BOSType) -> BOS:
    return BOS(
        index=index,
        timestamp=datetime(2025, 1, 1),
        price=100,
        type=bos_type,
    )


def make_choch(index: int, choch_type: CHOCHType) -> CHOCH:
    return CHOCH(
        index=index,
        timestamp=datetime(2025, 1, 1),
        price=100,
        type=choch_type,
    )


def test_keep_range_when_no_events():
    state = MarketStructureState()

    engine = TrendEngine()

    engine.update(state)

    assert state.trend == Trend.RANGE


def test_set_bullish_from_bullish_bos():
    state = MarketStructureState()

    state.last_bos = make_bos(1, BOSType.BULLISH)

    engine = TrendEngine()

    engine.update(state)

    assert state.trend == Trend.BULLISH


def test_set_bearish_from_bearish_bos():
    state = MarketStructureState()

    state.last_bos = make_bos(1, BOSType.BEARISH)

    engine = TrendEngine()

    engine.update(state)

    assert state.trend == Trend.BEARISH


def test_set_bullish_from_bullish_choch():
    state = MarketStructureState()

    state.last_choch = make_choch(1, CHOCHType.BULLISH)

    engine = TrendEngine()

    engine.update(state)

    assert state.trend == Trend.BULLISH


def test_set_bearish_from_bearish_choch():
    state = MarketStructureState()

    state.last_choch = make_choch(1, CHOCHType.BEARISH)

    engine = TrendEngine()

    engine.update(state)

    assert state.trend == Trend.BEARISH


def test_bos_wins_when_newer():
    state = MarketStructureState()

    state.last_choch = make_choch(1, CHOCHType.BEARISH)
    state.last_bos = make_bos(2, BOSType.BULLISH)

    engine = TrendEngine()

    engine.update(state)

    assert state.trend == Trend.BULLISH


def test_choch_wins_when_newer():
    state = MarketStructureState()

    state.last_bos = make_bos(1, BOSType.BEARISH)
    state.last_choch = make_choch(2, CHOCHType.BULLISH)

    engine = TrendEngine()

    engine.update(state)

    assert state.trend == Trend.BULLISH
