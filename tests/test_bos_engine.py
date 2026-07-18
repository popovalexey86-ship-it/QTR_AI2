from datetime import datetime

from core.bos_engine import BOSEngine
from core.bos_type import BOSType
from core.market_structure_state import MarketStructureState
from core.structure import Structure
from core.structure_type import StructureType


def make_structure(price: float, structure_type: StructureType) -> Structure:
    return Structure(
        index=0,
        timestamp=datetime(2025, 1, 1),
        price=price,
        type=structure_type,
    )


def test_no_bos_when_no_previous_hh():
    state = MarketStructureState()

    state.last_hh = make_structure(100, StructureType.HH)

    engine = BOSEngine()

    assert engine.detect(state) is None


def test_no_bos_when_no_previous_ll():
    state = MarketStructureState()

    state.last_ll = make_structure(100, StructureType.LL)

    engine = BOSEngine()

    assert engine.detect(state) is None


def test_detect_bullish_bos():
    state = MarketStructureState()

    state.previous_hh = make_structure(100, StructureType.HH)
    state.last_hh = make_structure(120, StructureType.HH)

    engine = BOSEngine()

    bos = engine.detect(state)

    assert bos is not None
    assert bos.type == BOSType.BULLISH


def test_detect_bearish_bos():
    state = MarketStructureState()

    state.previous_ll = make_structure(100, StructureType.LL)
    state.last_ll = make_structure(80, StructureType.LL)

    engine = BOSEngine()

    bos = engine.detect(state)

    assert bos is not None
    assert bos.type == BOSType.BEARISH


def test_no_bullish_bos_when_hh_not_higher():
    state = MarketStructureState()

    state.previous_hh = make_structure(100, StructureType.HH)
    state.last_hh = make_structure(100, StructureType.HH)

    engine = BOSEngine()

    assert engine.detect(state) is None


def test_no_bearish_bos_when_ll_not_lower():
    state = MarketStructureState()

    state.previous_ll = make_structure(100, StructureType.LL)
    state.last_ll = make_structure(100, StructureType.LL)

    engine = BOSEngine()

    assert engine.detect(state) is None
