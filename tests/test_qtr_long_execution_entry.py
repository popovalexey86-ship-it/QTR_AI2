from datetime import UTC, datetime

from core.candle import Candle
from core.fair_value_gap import (
    FairValueGap,
    FairValueGapDirection,
    FairValueGapStatus,
)
from core.order_block import OrderBlock, OrderBlockDirection, OrderBlockStatus
from core.structure_type import StructureType
from strategies.qtr_long.displacement import LongDisplacement
from strategies.qtr_long.execution_entry import (
    LongExecutionEntryEngine,
    LongExecutionZoneSource,
)
from strategies.qtr_long.execution_raid import LongLiquidityRaid
from strategies.qtr_long.execution_structure import (
    LongStructureShift,
    LongStructureShiftType,
)
from strategies.qtr_long.liquidity_map import SellSideLiquidityLevel


NOW = datetime(2026, 9, 5, tzinfo=UTC)


def _candle(index: int, *, low: float = 98.0, close: float = 101.0) -> Candle:
    return Candle(
        timestamp=NOW,
        open=99.0,
        high=102.0,
        low=low,
        close=close,
        volume=1.0,
        index=index,
    )


def _raid(index: int = 10) -> LongLiquidityRaid:
    return LongLiquidityRaid(
        level=SellSideLiquidityLevel(
            price=100.0,
            source_index=5,
            source_timestamp=NOW,
            source_type=StructureType.HL,
        ),
        candle=_candle(index, low=97.0, close=101.0),
    )


def _displacement(index: int = 11) -> LongDisplacement:
    return LongDisplacement(
        candle=_candle(index, low=100.0, close=105.0),
        body_ratio=0.7,
        range_expansion=1.5,
        close_location=0.9,
    )


def _shift(index: int = 12) -> LongStructureShift:
    return LongStructureShift(
        type=LongStructureShiftType.MSS,
        index=index,
        price=105.0,
    )


def _fvg(
    *,
    index: int = 11,
    low: float = 101.0,
    high: float = 103.0,
    direction: FairValueGapDirection = FairValueGapDirection.BULLISH,
    status: FairValueGapStatus = FairValueGapStatus.OPEN,
) -> FairValueGap:
    return FairValueGap(
        index=index,
        timestamp=NOW,
        direction=direction,
        low=low,
        high=high,
        status=status,
    )


def _ob(
    *,
    index: int = 10,
    low: float = 100.0,
    high: float = 102.0,
    direction: OrderBlockDirection = OrderBlockDirection.BULLISH,
    status: OrderBlockStatus = OrderBlockStatus.FRESH,
) -> OrderBlock:
    return OrderBlock(
        index=index,
        timestamp=NOW,
        direction=direction,
        low=low,
        high=high,
        status=status,
    )


def test_builds_overlap_as_confluence_zone() -> None:
    plan = LongExecutionEntryEngine().build(
        raid=_raid(),
        displacement=_displacement(),
        structure_shift=_shift(),
        fair_value_gap=_fvg(low=101.0, high=103.0),
        order_block=_ob(low=100.0, high=102.0),
    )

    assert plan is not None
    assert plan.source == LongExecutionZoneSource.CONFLUENCE
    assert plan.zone_low == 101.0
    assert plan.zone_high == 102.0
    assert plan.entry == 101.5


def test_uses_bullish_fvg_when_no_order_block() -> None:
    plan = LongExecutionEntryEngine().build(
        raid=_raid(),
        displacement=_displacement(),
        structure_shift=_shift(),
        fair_value_gap=_fvg(),
        order_block=None,
    )

    assert plan is not None
    assert plan.source == LongExecutionZoneSource.FVG
    assert plan.entry == 102.0


def test_uses_bullish_order_block_when_no_fvg() -> None:
    plan = LongExecutionEntryEngine().build(
        raid=_raid(),
        displacement=_displacement(),
        structure_shift=_shift(),
        fair_value_gap=None,
        order_block=_ob(),
    )

    assert plan is not None
    assert plan.source == LongExecutionZoneSource.ORDER_BLOCK
    assert plan.entry == 101.0


def test_non_overlapping_valid_zones_prefer_fvg() -> None:
    plan = LongExecutionEntryEngine().build(
        raid=_raid(),
        displacement=_displacement(),
        structure_shift=_shift(),
        fair_value_gap=_fvg(low=103.0, high=104.0),
        order_block=_ob(low=100.0, high=102.0),
    )

    assert plan is not None
    assert plan.source == LongExecutionZoneSource.FVG
    assert plan.zone_low == 103.0
    assert plan.zone_high == 104.0


def test_rejects_bearish_execution_zones() -> None:
    plan = LongExecutionEntryEngine().build(
        raid=_raid(),
        displacement=_displacement(),
        structure_shift=_shift(),
        fair_value_gap=_fvg(direction=FairValueGapDirection.BEARISH),
        order_block=_ob(direction=OrderBlockDirection.BEARISH),
    )

    assert plan is None


def test_rejects_filled_or_invalidated_execution_zones() -> None:
    plan = LongExecutionEntryEngine().build(
        raid=_raid(),
        displacement=_displacement(),
        structure_shift=_shift(),
        fair_value_gap=_fvg(status=FairValueGapStatus.FILLED),
        order_block=_ob(status=OrderBlockStatus.INVALIDATED),
    )

    assert plan is None


def test_rejects_zones_created_before_raid() -> None:
    plan = LongExecutionEntryEngine().build(
        raid=_raid(index=10),
        displacement=_displacement(index=11),
        structure_shift=_shift(index=12),
        fair_value_gap=_fvg(index=9),
        order_block=_ob(index=8),
    )

    assert plan is None


def test_rejects_zones_not_yet_available_at_structure_confirmation() -> None:
    plan = LongExecutionEntryEngine().build(
        raid=_raid(index=10),
        displacement=_displacement(index=11),
        structure_shift=_shift(index=12),
        fair_value_gap=_fvg(index=13),
        order_block=_ob(index=14),
    )

    assert plan is None


def test_rejects_invalid_execution_chronology() -> None:
    plan = LongExecutionEntryEngine().build(
        raid=_raid(index=10),
        displacement=_displacement(index=9),
        structure_shift=_shift(index=12),
        fair_value_gap=_fvg(index=11),
        order_block=None,
    )
    assert plan is None

    plan = LongExecutionEntryEngine().build(
        raid=_raid(index=10),
        displacement=_displacement(index=11),
        structure_shift=_shift(index=10),
        fair_value_gap=_fvg(index=11),
        order_block=None,
    )
    assert plan is None


def test_stop_is_anchored_below_zone_and_raid_extreme() -> None:
    plan = LongExecutionEntryEngine().build(
        raid=_raid(),
        displacement=_displacement(),
        structure_shift=_shift(),
        fair_value_gap=_fvg(low=101.0, high=103.0),
        order_block=None,
    )

    assert plan is not None
    assert plan.stop_loss == 97.0
    assert plan.stop_loss < plan.entry
