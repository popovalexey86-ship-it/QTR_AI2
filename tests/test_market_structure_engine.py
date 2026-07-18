from datetime import datetime

from core.market_structure_state import MarketStructureState
from core.structure import Structure
from core.structure_type import StructureType
from market_structure.market_structure_engine import MarketStructureEngine


def structure(structure_type: StructureType, price: float = 100.0) -> Structure:
    return Structure(
        index=0,
        timestamp=datetime(2025, 1, 1),
        price=price,
        type=structure_type,
    )


def test_empty_structure_list():
    engine = MarketStructureEngine()
    state = MarketStructureState()

    engine.update(state, [])

    assert state.last_hh is None
    assert state.last_hl is None
    assert state.last_lh is None
    assert state.last_ll is None


def test_update_last_hh():
    engine = MarketStructureEngine()
    state = MarketStructureState()

    engine.update(
        state,
        [structure(StructureType.HH, 100)],
    )

    assert state.last_hh is not None
    assert state.last_hh.price == 100


def test_update_last_hl():
    engine = MarketStructureEngine()
    state = MarketStructureState()

    engine.update(
        state,
        [structure(StructureType.HL, 90)],
    )

    assert state.last_hl is not None
    assert state.last_hl.price == 90


def test_update_last_lh():
    engine = MarketStructureEngine()
    state = MarketStructureState()

    engine.update(
        state,
        [structure(StructureType.LH, 110)],
    )

    assert state.last_lh is not None
    assert state.last_lh.price == 110


def test_update_last_ll():
    engine = MarketStructureEngine()
    state = MarketStructureState()

    engine.update(
        state,
        [structure(StructureType.LL, 80)],
    )

    assert state.last_ll is not None
    assert state.last_ll.price == 80


def test_keep_latest_structure_of_each_type():
    engine = MarketStructureEngine()
    state = MarketStructureState()

    engine.update(
        state,
        [
            structure(StructureType.HH, 100),
            structure(StructureType.HH, 120),
            structure(StructureType.HL, 90),
            structure(StructureType.HL, 95),
            structure(StructureType.LH, 110),
            structure(StructureType.LH, 105),
            structure(StructureType.LL, 80),
            structure(StructureType.LL, 70),
        ],
    )

    assert state.last_hh.price == 120
    assert state.last_hl.price == 95
    assert state.last_lh.price == 105
    assert state.last_ll.price == 70
    
def test_shift_previous_hh():
    engine = MarketStructureEngine()
    state = MarketStructureState()

    first = structure(StructureType.HH, 100)
    second = structure(StructureType.HH, 120)

    engine.update(state, [first])

    assert state.previous_hh is None
    assert state.last_hh == first

    engine.update(state, [second])

    assert state.previous_hh == first
    assert state.last_hh == second
    
def test_shift_previous_ll():
    engine = MarketStructureEngine()
    state = MarketStructureState()

    first = structure(StructureType.LL, 80)
    second = structure(StructureType.LL, 70)

    engine.update(state, [first])

    assert state.previous_ll is None
    assert state.last_ll == first

    engine.update(state, [second])

    assert state.previous_ll == first
    assert state.last_ll == second