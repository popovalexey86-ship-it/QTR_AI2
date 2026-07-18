from datetime import datetime, timedelta

from core.structure_type import StructureType
from core.swing import Swing
from core.swing_type import SwingType
from market_structure.structure_engine import StructureEngine


def create_swings_hh():
    start = datetime(2025, 1, 1)

    return [
        Swing(index=2, timestamp=start, price=100, type=SwingType.HIGH),
        Swing(index=8, timestamp=start + timedelta(minutes=30), price=110, type=SwingType.HIGH),
    ]


def create_swings_hl():
    start = datetime(2025, 1, 1)

    return [
        Swing(index=2, timestamp=start, price=100, type=SwingType.LOW),
        Swing(index=8, timestamp=start + timedelta(minutes=30), price=110, type=SwingType.LOW),
    ]


def create_swings_lh():
    start = datetime(2025, 1, 1)

    return [
        Swing(index=2, timestamp=start, price=110, type=SwingType.HIGH),
        Swing(index=8, timestamp=start + timedelta(minutes=30), price=100, type=SwingType.HIGH),
    ]


def create_swings_ll():
    start = datetime(2025, 1, 1)

    return [
        Swing(index=2, timestamp=start, price=110, type=SwingType.LOW),
        Swing(index=8, timestamp=start + timedelta(minutes=30), price=100, type=SwingType.LOW),
    ]


def test_detect_higher_high():
    swings = create_swings_hh()

    engine = StructureEngine()

    structures = engine.detect(swings)

    assert len(structures) == 1
    assert structures[0].type == StructureType.HH


def test_detect_higher_low():
    swings = create_swings_hl()

    engine = StructureEngine()

    structures = engine.detect(swings)

    assert len(structures) == 1
    assert structures[0].type == StructureType.HL


def test_detect_lower_high():
    swings = create_swings_lh()

    engine = StructureEngine()

    structures = engine.detect(swings)

    assert len(structures) == 1
    assert structures[0].type == StructureType.LH


def test_detect_lower_low():
    swings = create_swings_ll()

    engine = StructureEngine()

    structures = engine.detect(swings)

    assert len(structures) == 1
    assert structures[0].type == StructureType.LL