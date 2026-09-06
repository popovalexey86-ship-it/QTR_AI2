from dataclasses import dataclass
from enum import Enum

from core.fair_value_gap import (
    FairValueGap,
    FairValueGapDirection,
    FairValueGapStatus,
)
from core.order_block import OrderBlock, OrderBlockDirection, OrderBlockStatus
from strategies.qtr_long.dealing_range import DealingRange, DealingRangeZone


class LongPOIDecision(Enum):
    """Whether the 15m layer contains a valid area to hunt a 5m LONG trigger."""

    ALLOW = "allow"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class LongPOI:
    """15m point/area of interest for the hierarchical QTR Long model.

    This is not an entry signal. A valid POI only grants permission to descend
    to the 5m execution layer and wait for a separate liquidity raid,
    displacement and structural confirmation.
    """

    order_block: OrderBlock
    dealing_range: DealingRange
    zone: DealingRangeZone
    fair_value_gap: FairValueGap | None = None

    @property
    def low(self) -> float:
        return self.order_block.low

    @property
    def high(self) -> float:
        return self.order_block.high


@dataclass(frozen=True, slots=True)
class LongPOIResult:
    decision: LongPOIDecision
    poi: LongPOI | None
    reason: str


class LongPOIEngine:
    """15m structural POI gate with relaxed location permission.

    The active Order Block is still required to be bullish and valid, but its
    midpoint may now sit anywhere inside the confirmed 1H dealing range:
    discount, equilibrium or premium. Only locations outside the structural
    range are rejected. This lets 5m execution evidence decide whether a
    premium-location setup is actually tradable instead of blocking it early.

    A bullish active FVG remains optional confluence when it overlaps the OB.
    """

    _ALLOWED_ZONES = {
        DealingRangeZone.DISCOUNT,
        DealingRangeZone.EQUILIBRIUM,
        DealingRangeZone.PREMIUM,
    }

    def evaluate(
        self,
        *,
        dealing_range: DealingRange | None,
        order_block: OrderBlock | None,
        fair_value_gap: FairValueGap | None = None,
    ) -> LongPOIResult:
        if dealing_range is None:
            return LongPOIResult(LongPOIDecision.BLOCK, None, "missing dealing range")

        if order_block is None:
            return LongPOIResult(LongPOIDecision.BLOCK, None, "missing order block")

        if order_block.direction != OrderBlockDirection.BULLISH:
            return LongPOIResult(LongPOIDecision.BLOCK, None, "order block is not bullish")

        if order_block.status == OrderBlockStatus.INVALIDATED:
            return LongPOIResult(LongPOIDecision.BLOCK, None, "order block is invalidated")

        zone = dealing_range.locate(order_block.midpoint)
        if zone not in self._ALLOWED_ZONES:
            return LongPOIResult(
                LongPOIDecision.BLOCK,
                None,
                f"order block location is {zone.value}",
            )

        linked_fvg = self._linked_bullish_fvg(order_block, fair_value_gap)
        poi = LongPOI(
            order_block=order_block,
            dealing_range=dealing_range,
            zone=zone,
            fair_value_gap=linked_fvg,
        )
        return LongPOIResult(LongPOIDecision.ALLOW, poi, "valid 15m long POI")

    @staticmethod
    def _linked_bullish_fvg(
        order_block: OrderBlock,
        fair_value_gap: FairValueGap | None,
    ) -> FairValueGap | None:
        if fair_value_gap is None:
            return None
        if fair_value_gap.direction != FairValueGapDirection.BULLISH:
            return None
        if fair_value_gap.status == FairValueGapStatus.FILLED:
            return None

        overlaps = (
            fair_value_gap.low <= order_block.high
            and fair_value_gap.high >= order_block.low
        )
        return fair_value_gap if overlaps else None
