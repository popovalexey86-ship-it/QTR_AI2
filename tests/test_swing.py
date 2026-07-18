from datetime import datetime

from core.swing import Swing
from core.swing_type import SwingType


def test_create_swing():

    swing = Swing(
        index=10,
        timestamp=datetime(2025, 1, 1, 12, 0),
        price=105000,
        type=SwingType.HIGH,
    )

    assert swing.index == 10
    assert swing.price == 105000
    assert swing.type == SwingType.HIGH


def test_swing_is_immutable():

    import pytest

    swing = Swing(
        index=0,
        timestamp=datetime.now(),
        price=100,
        type=SwingType.LOW,
    )

    with pytest.raises(AttributeError):
        swing.price = 200