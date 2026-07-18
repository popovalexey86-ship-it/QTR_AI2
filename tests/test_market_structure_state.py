from datetime import datetime

from core.market_structure_state import MarketStructureState
from core.structure import Structure
from core.structure_type import StructureType
from core.trend import Trend


def test_default_market_structure_state():
    state = MarketStructureState()

    assert state.trend == Trend.RANGE

    assert state.last_hh is None
    assert state.last_hl is None
    assert state.last_lh is None
    assert state.last_ll is None

    assert state.last_bos is None
    assert state.last_choch is None


def test_update_market_structure_state():

    hh = Structure(
        index=10,
        timestamp=datetime(2025, 1, 1),
        price=50000,
        type=StructureType.HH,
    )

    state = MarketStructureState()

    state.last_hh = hh

    assert state.last_hh == hh
    