from datetime import datetime

from core.choch_engine import CHOCHEngine
from core.choch_type import CHOCHType
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


def test_no_choch_when_no_previous_hl():
    state = MarketStructureState()

    state.last_hl = make_structure(100, StructureType.HL)

    engine = CHOCHEngine()

    assert engine.detect(state) is None


def test_no_choch_when_no_previous_lh():
    state = MarketStructureState()

    state.last_lh = make_structure(100, StructureType.LH)

    engine = CHOCHEngine()

    assert engine.detect(state) is None


def test_detect_bearish_choch():
    state = MarketStructureState()

    state.previous_hl = make_structure(100, StructureType.HL)
    state.last_hl = make_structure(80, StructureType.HL)

    engine = CHOCHEngine()

    choch = engine.detect(state)

    assert choch is not None
    assert choch.type == CHOCHType.BEARISH
    assert choch.price == 80


def test_detect_bullish_choch():
    state = MarketStructureState()

    state.previous_lh = make_structure(100, StructureType.LH)
    state.last_lh = make_structure(120, StructureType.LH)

    engine = CHOCHEngine()

    choch = engine.detect(state)

    assert choch is not None
    assert choch.type == CHOCHType.BULLISH
    assert choch.price == 120


def test_no_bearish_choch_when_hl_not_lower():
    state = MarketStructureState()

    state.previous_hl = make_structure(100, StructureType.HL)
    state.last_hl = make_structure(100, StructureType.HL)

    engine = CHOCHEngine()

    assert engine.detect(state) is None


def test_no_bullish_choch_when_lh_not_higher():
    state = MarketStructureState()

    state.previous_lh = make_structure(100, StructureType.LH)
    state.last_lh = make_structure(100, StructureType.LH)

    engine = CHOCHEngine()

    assert engine.detect(state) is None
