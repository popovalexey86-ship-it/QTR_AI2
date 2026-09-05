from dataclasses import dataclass
from enum import Enum

from core.fair_value_gap import (
    FairValueGap,
    FairValueGapDirection,
    FairValueGapStatus,
)
from core.order_block import OrderBlock, OrderBlockDirection, OrderBlockStatus
from strategies.qtr_long.displacement import LongDisplacement
from strategies.qtr_long.execution_raid import LongLiquidityRaid
from strategies.qtr_long.execution_structure import LongStructureShift


class LongExecutionZoneSource(Enum):
    FVG = "fvg"
    ORDER_BLOCK = "order_block"
    CONFLUENCE = "confluence"


@dataclass(frozen=True, slots=True)
class LongExecutionEntryPlan:
    """Pending BUY plan for a future 5m retrace into execution value.

    The plan is created only after the raid -> displacement -> bullish structure
    sequence is complete. It does not wait for a future retrace candle and
    therefore avoids lookahead: the broker may place a resting limit order at
    ``entry`` and let later price action decide whether it is filled.
    """

    source: LongExecutionZoneSource
    zone_low: float
    zone_high: float
    entry: float
    stop_loss: float

    def __post_init__(self) -> None:
        if self.zone_low >= self.zone_high:
            raise ValueError("execution zone low must be below high")
        if not self.zone_low <= self.entry <= self.zone_high:
            raise ValueError("entry must be inside execution zone")
        if self.stop_loss >= self.entry:
            raise ValueError("stop_loss must be below entry")


class LongExecutionEntryEngine:
    """Build a LONG-only limit-entry plan from a valid 5m execution POI.

    Qualifying execution value must be bullish, still active, formed no earlier
    than the liquidity raid and no later than the confirmed structural shift.
    If a bullish FVG and bullish Order Block overlap, their intersection is used
    as the highest-confluence execution zone. Otherwise the FVG is preferred,
    with the Order Block as a fallback.

    This engine creates only a BUY plan or nothing. It never creates SELL/SHORT
    permission.
    """

    def build(
        self,
        *,
        raid: LongLiquidityRaid,
        displacement: LongDisplacement,
        structure_shift: LongStructureShift,
        fair_value_gap: FairValueGap | None,
        order_block: OrderBlock | None,
    ) -> LongExecutionEntryPlan | None:
        if displacement.candle.index < raid.candle.index:
            return None
        if structure_shift.index < displacement.candle.index:
            return None

        fvg = self._valid_fvg(
            fair_value_gap,
            start_index=raid.candle.index,
            end_index=structure_shift.index,
        )
        ob = self._valid_order_block(
            order_block,
            start_index=raid.candle.index,
            end_index=structure_shift.index,
        )

        source: LongExecutionZoneSource
        zone_low: float
        zone_high: float

        if fvg is not None and ob is not None:
            overlap_low = max(fvg.low, ob.low)
            overlap_high = min(fvg.high, ob.high)
            if overlap_low < overlap_high:
                source = LongExecutionZoneSource.CONFLUENCE
                zone_low = overlap_low
                zone_high = overlap_high
            else:
                source = LongExecutionZoneSource.FVG
                zone_low = fvg.low
                zone_high = fvg.high
        elif fvg is not None:
            source = LongExecutionZoneSource.FVG
            zone_low = fvg.low
            zone_high = fvg.high
        elif ob is not None:
            source = LongExecutionZoneSource.ORDER_BLOCK
            zone_low = ob.low
            zone_high = ob.high
        else:
            return None

        entry = (zone_low + zone_high) / 2.0
        stop_loss = min(zone_low, raid.extreme_price)
        if stop_loss >= entry:
            return None

        return LongExecutionEntryPlan(
            source=source,
            zone_low=zone_low,
            zone_high=zone_high,
            entry=entry,
            stop_loss=stop_loss,
        )

    @staticmethod
    def _valid_fvg(
        fvg: FairValueGap | None,
        *,
        start_index: int,
        end_index: int,
    ) -> FairValueGap | None:
        if fvg is None:
            return None
        if fvg.direction != FairValueGapDirection.BULLISH:
            return None
        if fvg.status == FairValueGapStatus.FILLED:
            return None
        if not start_index <= fvg.index <= end_index:
            return None
        return fvg

    @staticmethod
    def _valid_order_block(
        order_block: OrderBlock | None,
        *,
        start_index: int,
        end_index: int,
    ) -> OrderBlock | None:
        if order_block is None:
            return None
        if order_block.direction != OrderBlockDirection.BULLISH:
            return None
        if order_block.status == OrderBlockStatus.INVALIDATED:
            return None
        if not start_index <= order_block.index <= end_index:
            return None
        return order_block
