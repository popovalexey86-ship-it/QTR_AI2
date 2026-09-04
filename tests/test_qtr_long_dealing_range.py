from datetime import datetime

import pytest

from core.swing import Swing
from core.swing_type import SwingType
from strategies.qtr_long.dealing_range import (
    DealingRange,
    DealingRangeEngine,
    DealingRangeZone,
)


def swing(index: int, price: float, swing_type: SwingType) -> Swing:
    return Swing(
        index=index,
        timestamp=datetime(2026, 1, 1, index),
        price=price,
        type=swing_type,
    )


def test_builds_range_from_latest_confirmed_high_and_low():
    result = DealingRangeEngine().build(
        [
            swing(1, 90, SwingType.LOW),
            swing(2, 110, SwingType.HIGH),
            swing(3, 95, SwingType.LOW),
            swing(4, 120, SwingType.HIGH),
        ]
    )

    assert result is not None
    assert result.low == 95
    assert result.high == 120
    assert result.equilibrium == 107.5


def test_requires_both_sides_of_range():
    assert DealingRangeEngine().build([swing(1, 90, SwingType.LOW)]) is None


def test_rejects_inverted_latest_swing_prices():
    result = DealingRangeEngine().build(
        [
            swing(1, 120, SwingType.LOW),
            swing(2, 110, SwingType.HIGH),
        ]
    )
    assert result is None


def test_locates_discount_equilibrium_and_premium():
    dealing_range = DealingRange(
        low_swing=swing(1, 100, SwingType.LOW),
        high_swing=swing(2, 200, SwingType.HIGH),
        equilibrium=150,
    )

    assert dealing_range.locate(120) == DealingRangeZone.DISCOUNT
    assert dealing_range.locate(150) == DealingRangeZone.EQUILIBRIUM
    assert dealing_range.locate(180) == DealingRangeZone.PREMIUM


def test_locates_price_outside_range_explicitly():
    dealing_range = DealingRange(
        low_swing=swing(1, 100, SwingType.LOW),
        high_swing=swing(2, 200, SwingType.HIGH),
        equilibrium=150,
    )

    assert dealing_range.locate(99) == DealingRangeZone.BELOW_RANGE
    assert dealing_range.locate(201) == DealingRangeZone.ABOVE_RANGE


def test_position_is_normalized_inside_range():
    dealing_range = DealingRange(
        low_swing=swing(1, 100, SwingType.LOW),
        high_swing=swing(2, 200, SwingType.HIGH),
        equilibrium=150,
    )

    assert dealing_range.position(125) == pytest.approx(0.25)


def test_equilibrium_band_must_be_valid():
    dealing_range = DealingRange(
        low_swing=swing(1, 100, SwingType.LOW),
        high_swing=swing(2, 200, SwingType.HIGH),
        equilibrium=150,
    )

    with pytest.raises(ValueError):
        dealing_range.locate(150, equilibrium_band=0.5)
