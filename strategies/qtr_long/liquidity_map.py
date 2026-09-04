from dataclasses import dataclass
from datetime import datetime

from core.market_structure_state import MarketStructureState
from core.structure import Structure
from core.structure_type import StructureType


@dataclass(frozen=True, slots=True)
class SellSideLiquidityLevel:
    """Confirmed downside liquidity reference relevant to a future LONG raid."""

    price: float
    source_index: int
    source_timestamp: datetime
    source_type: StructureType


@dataclass(frozen=True, slots=True)
class LongLiquidityMap:
    """Sell-side liquidity references that a LONG setup may raid before reversal."""

    sell_side: tuple[SellSideLiquidityLevel, ...]

    @property
    def has_sell_side_liquidity(self) -> bool:
        return bool(self.sell_side)


class LongLiquidityMapEngine:
    """Build a conservative sell-side liquidity map from confirmed 15m structure.

    QTR Long is interested in downside liquidity that price may sweep before a
    bullish execution sequence. At this milestone we intentionally use only
    confirmed HL/LL structure references; equal-lows clustering can be added as
    a separate evidence source later without changing the contract.
    """

    def build(self, state: MarketStructureState | None) -> LongLiquidityMap:
        if state is None:
            return LongLiquidityMap(sell_side=())

        structures = [
            item
            for item in (state.previous_hl, state.last_hl, state.previous_ll, state.last_ll)
            if item is not None
        ]
        unique = self._deduplicate(structures)
        levels = tuple(
            SellSideLiquidityLevel(
                price=item.price,
                source_index=item.index,
                source_timestamp=item.timestamp,
                source_type=item.type,
            )
            for item in sorted(unique, key=lambda structure: structure.index, reverse=True)
        )
        return LongLiquidityMap(sell_side=levels)

    @staticmethod
    def _deduplicate(structures: list[Structure]) -> list[Structure]:
        latest_by_price: dict[float, Structure] = {}
        for structure in structures:
            if structure.type not in (StructureType.HL, StructureType.LL):
                continue
            existing = latest_by_price.get(structure.price)
            if existing is None or structure.index > existing.index:
                latest_by_price[structure.price] = structure
        return list(latest_by_price.values())
