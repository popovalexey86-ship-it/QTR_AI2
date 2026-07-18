from core.swing_type import SwingType


def test_swing_type_values():

    assert SwingType.HIGH.value == "HIGH"
    assert SwingType.LOW.value == "LOW"