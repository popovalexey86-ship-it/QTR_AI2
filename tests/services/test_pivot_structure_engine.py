from datetime import UTC, datetime

from core.structure_type import StructureType
from core.swing import Swing
from core.swing_type import SwingType

from services.pivot_structure_engine import PivotStructureEngine


def test_detect_higher_high():
    swings = [
        Swing(
            index=1,
            timestamp=datetime.now(UTC),
            price=100,
            type=SwingType.HIGH,
        ),
        Swing(
            index=3,
            timestamp=datetime.now(UTC),
            price=110,
            type=SwingType.HIGH,
        ),
    ]

    engine = PivotStructureEngine()

    structure = engine.build(swings)

    assert len(structure) == 1
    assert structure[0].type == StructureType.HH


def test_detect_lower_high():
    swings = [
        Swing(
            index=1,
            timestamp=datetime.now(UTC),
            price=110,
            type=SwingType.HIGH,
        ),
        Swing(
            index=3,
            timestamp=datetime.now(UTC),
            price=100,
            type=SwingType.HIGH,
        ),
    ]

    engine = PivotStructureEngine()

    structure = engine.build(swings)

    assert len(structure) == 1
    assert structure[0].type == StructureType.LH


def test_detect_higher_low():
    swings = [
        Swing(
            index=1,
            timestamp=datetime.now(UTC),
            price=90,
            type=SwingType.LOW,
        ),
        Swing(
            index=3,
            timestamp=datetime.now(UTC),
            price=95,
            type=SwingType.LOW,
        ),
    ]

    engine = PivotStructureEngine()

    structure = engine.build(swings)

    assert len(structure) == 1
    assert structure[0].type == StructureType.HL


def test_detect_lower_low():
    swings = [
        Swing(
            index=1,
            timestamp=datetime.now(UTC),
            price=95,
            type=SwingType.LOW,
        ),
        Swing(
            index=3,
            timestamp=datetime.now(UTC),
            price=90,
            type=SwingType.LOW,
        ),
    ]

    engine = PivotStructureEngine()

    structure = engine.build(swings)

    assert len(structure) == 1
    assert structure[0].type == StructureType.LL


def test_ignore_opposite_swing_type():
    swings = [
        Swing(
            index=1,
            timestamp=datetime.now(UTC),
            price=100,
            type=SwingType.HIGH,
        ),
        Swing(
            index=2,
            timestamp=datetime.now(UTC),
            price=90,
            type=SwingType.LOW,
        ),
        Swing(
            index=3,
            timestamp=datetime.now(UTC),
            price=110,
            type=SwingType.HIGH,
        ),
    ]

    engine = PivotStructureEngine()

    structure = engine.build(swings)

    assert len(structure) == 1
    assert structure[0].type == StructureType.HH
