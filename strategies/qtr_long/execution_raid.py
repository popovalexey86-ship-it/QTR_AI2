from dataclasses import dataclass

from core.candle import Candle
from strategies.qtr_long.liquidity_map import LongLiquidityMap, SellSideLiquidityLevel


@dataclass(frozen=True, slots=True)
class LongLiquidityRaid:
    """5m sweep and reclaim of mapped sell-side liquidity."""

    level: SellSideLiquidityLevel
    candle: Candle

    @property
    def extreme_price(self) -> float:
        return self.candle.low

    @property
    def reclaim_close(self) -> float:
        return self.candle.close


class LongLiquidityRaidDetector:
    """Detect a bullish 5m raid of mapped 15m sell-side liquidity.

    Candidate B still requires price to trade strictly below mapped sell-side
    liquidity, but a close exactly back on the reclaimed level is now accepted.
    This removes an unnecessarily strict one-tick-style rejection without
    turning a simple touch into a liquidity raid.
    """

    def detect(self, candle: Candle, liquidity_map: LongLiquidityMap) -> LongLiquidityRaid | None:
        candidates = [
            level
            for level in liquidity_map.sell_side
            if candle.low < level.price <= candle.close
        ]
        if not candidates:
            return None

        level = max(candidates, key=lambda item: item.price)
        return LongLiquidityRaid(level=level, candle=candle)
