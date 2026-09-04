from datetime import UTC, datetime

from core.fair_value_gap import (
    FairValueGap,
    FairValueGapDirection,
    FairValueGapStatus,
)
from core.order_block import OrderBlock, OrderBlockDirection, OrderBlockStatus
from core.swing import Swing
from core.swing_type import SwingType
from strategies.qtr_long.dealing_range import DealingRange, DealingRangeZone
from strategies.qtr_long.poi import LongPOIDecision, LongPOIEngine


def _range() -> DealingRange:
    low = Swing(
        index=10,
        timestamp=datetime(2026, 1, 1, 10, tzinfo=UTC),
        price=100.0,
        type=SwingType.LOW,
    )
    high = Swing(
        index=20,
        timestamp=datetime(2026, 1, 1, 20, tzinfo=UTC),
        price=200.0,
        type=SwingType.HIGH,
    )
    return DealingRange(low_swing=low, high_swing=high, equilibrium=150.0)


def _ob(
    *,
    low: float = 120.0,
    high: float = 130.0,
    direction: OrderBlockDirection = OrderBlockDirection.BULLISH,
    status: OrderBlockStatus = OrderBlockStatus.FRESH,
) -> OrderBlock:
    return OrderBlock(
        index=30,
        timestamp=datetime(2026, 1, 2, tzinfo=UTC),
        direction=direction,
        low=low,
        high=high,
        status=status,
    )


def _fvg(
    *,
    low: float = 125.0,
    high: float = 135.0,
    direction: FairValueGapDirection = FairValueGapDirection.BULLISH,
    status: FairValueGapStatus = FairValueGapStatus.OPEN,
) -> FairValueGap:
    return FairValueGap(
        index=31,
        timestamp=datetime(2026, 1, 2, 0, 15, tzinfo=UTC),
        direction=direction,
        low=low,
        high=high,
        status=status,
    )


def test_discount_bullish_order_block_allows_poi() -> None:
    result = LongPOIEngine().evaluate(dealing_range=_range(), order_block=_ob())

    assert result.decision == LongPOIDecision.ALLOW
    assert result.poi is not None
    assert result.poi.zone == DealingRangeZone.DISCOUNT


def test_equilibrium_bullish_order_block_allows_poi() -> None:
    result = LongPOIEngine().evaluate(
        dealing_range=_range(),
        order_block=_ob(low=145.0, high=155.0),
    )

    assert result.decision == LongPOIDecision.ALLOW
    assert result.poi is not None
    assert result.poi.zone == DealingRangeZone.EQUILIBRIUM


def test_premium_order_block_is_blocked() -> None:
    result = LongPOIEngine().evaluate(
        dealing_range=_range(),
        order_block=_ob(low=170.0, high=180.0),
    )

    assert result.decision == LongPOIDecision.BLOCK
    assert result.poi is None


def test_bearish_order_block_is_blocked() -> None:
    result = LongPOIEngine().evaluate(
        dealing_range=_range(),
        order_block=_ob(direction=OrderBlockDirection.BEARISH),
    )

    assert result.decision == LongPOIDecision.BLOCK


def test_invalidated_order_block_is_blocked() -> None:
    result = LongPOIEngine().evaluate(
        dealing_range=_range(),
        order_block=_ob(status=OrderBlockStatus.INVALIDATED),
    )

    assert result.decision == LongPOIDecision.BLOCK


def test_missing_structural_inputs_are_blocked() -> None:
    engine = LongPOIEngine()

    assert engine.evaluate(dealing_range=None, order_block=_ob()).decision == LongPOIDecision.BLOCK
    assert engine.evaluate(dealing_range=_range(), order_block=None).decision == LongPOIDecision.BLOCK


def test_overlapping_active_bullish_fvg_is_linked_as_confluence() -> None:
    fvg = _fvg()
    result = LongPOIEngine().evaluate(
        dealing_range=_range(),
        order_block=_ob(),
        fair_value_gap=fvg,
    )

    assert result.decision == LongPOIDecision.ALLOW
    assert result.poi is not None
    assert result.poi.fair_value_gap == fvg


def test_fvg_cannot_rescue_invalid_location_and_unrelated_fvg_is_not_linked() -> None:
    engine = LongPOIEngine()

    premium = engine.evaluate(
        dealing_range=_range(),
        order_block=_ob(low=170.0, high=180.0),
        fair_value_gap=_fvg(low=170.0, high=180.0),
    )
    assert premium.decision == LongPOIDecision.BLOCK

    unrelated = engine.evaluate(
        dealing_range=_range(),
        order_block=_ob(),
        fair_value_gap=_fvg(low=140.0, high=145.0),
    )
    assert unrelated.decision == LongPOIDecision.ALLOW
    assert unrelated.poi is not None
    assert unrelated.poi.fair_value_gap is None


def test_filled_or_bearish_fvg_is_not_linked() -> None:
    engine = LongPOIEngine()

    filled = engine.evaluate(
        dealing_range=_range(),
        order_block=_ob(),
        fair_value_gap=_fvg(status=FairValueGapStatus.FILLED),
    )
    bearish = engine.evaluate(
        dealing_range=_range(),
        order_block=_ob(),
        fair_value_gap=_fvg(direction=FairValueGapDirection.BEARISH),
    )

    assert filled.poi is not None and filled.poi.fair_value_gap is None
    assert bearish.poi is not None and bearish.poi.fair_value_gap is None
