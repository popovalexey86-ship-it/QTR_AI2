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
    """Whether the 15m layer contains usable context to hunt a 5m LONG trigger."""

    ALLOW = "allow"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class LongPOI:
    """15m context for the hierarchical QTR Long model.

    Candidate B no longer requires a 15m Order Block. A valid bullish active
    FVG may provide the location context by itself. This layer is context only;
    it never creates an entry without the 5m execution sequence.
    """

    dealing_range: DealingRange
    zone: DealingRangeZone
    order_block: OrderBlock | None = None
    fair_value_gap: FairValueGap | None = None

    @property
    def low(self) -> float:
        if self.order_block is not None:
            return self.order_block.low
        if self.fair_value_gap is not None:
            return self.fair_value_gap.low
        raise RuntimeError("POI requires an order block or fair value gap")

    @property
    def high(self) -> float:
        if self.order_block is not None:
            return self.order_block.high
        if self.fair_value_gap is not None:
            return self.fair_value_gap.high
        raise RuntimeError("POI requires an order block or fair value gap")


@dataclass(frozen=True, slots=True)
class LongPOIResult:
    decision: LongPOIDecision
    poi: LongPOI | None
    reason: str


class LongPOIEngine:
    """Relaxed 15m context gate.

    A confirmed 1H dealing range is still required. Inside that range, either a
    valid bullish Order Block or a valid active bullish FVG is sufficient to let
    the strategy descend to 5m execution. Premium is allowed; only locations
    outside the structural range are rejected.
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

        valid_ob = self._valid_bullish_ob(order_block)
        valid_fvg = self._valid_bullish_fvg(fair_value_gap)

        if valid_ob is None and valid_fvg is None:
            return LongPOIResult(
                LongPOIDecision.BLOCK,
                None,
                "missing valid bullish 15m OB/FVG context",
            )

        anchor_low: float
        anchor_high: float
        if valid_ob is not None:
            anchor_low = valid_ob.low
            anchor_high = valid_ob.high
        else:
            assert valid_fvg is not None
            anchor_low = valid_fvg.low
            anchor_high = valid_fvg.high

        midpoint = (anchor_low + anchor_high) / 2.0
        zone = dealing_range.locate(midpoint)
        if zone not in self._ALLOWED_ZONES:
            return LongPOIResult(
                LongPOIDecision.BLOCK,
                None,
                f"15m context location is {zone.value}",
            )

        linked_fvg = valid_fvg
        if valid_ob is not None and valid_fvg is not None:
            overlaps = valid_fvg.low <= valid_ob.high and valid_fvg.high >= valid_ob.low
            if not overlaps:
                linked_fvg = None

        poi = LongPOI(
            dealing_range=dealing_range,
            zone=zone,
            order_block=valid_ob,
            fair_value_gap=linked_fvg,
        )
        source = "OB" if valid_ob is not None else "FVG"
        return LongPOIResult(
            LongPOIDecision.ALLOW,
            poi,
            f"valid 15m long context from {source}",
        )

    @staticmethod
    def _valid_bullish_ob(order_block: OrderBlock | None) -> OrderBlock | None:
        if order_block is None:
            return None
        if order_block.direction != OrderBlockDirection.BULLISH:
            return None
        if order_block.status == OrderBlockStatus.INVALIDATED:
            return None
        return order_block

    @staticmethod
    def _valid_bullish_fvg(fair_value_gap: FairValueGap | None) -> FairValueGap | None:
        if fair_value_gap is None:
            return None
        if fair_value_gap.direction != FairValueGapDirection.BULLISH:
            return None
        if fair_value_gap.status == FairValueGapStatus.FILLED:
            return None
        return fair_value_gap
