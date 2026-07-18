import pytest
from datetime import datetime

from core.structure import Structure
from core.structure_type import StructureType


def test_create_structure():

    structure = Structure(
        index=15,
        timestamp=datetime(2025, 1, 1, 12, 0),
        price=105000,
        type=StructureType.HH,
    )

    assert structure.index == 15
    assert structure.price == 105000
    assert structure.type == StructureType.HH


def test_structure_is_immutable():

    structure = Structure(
        index=1,
        timestamp=datetime.now(),
        price=100,
        type=StructureType.LL,
    )

    with pytest.raises(AttributeError):
        structure.price = 200
