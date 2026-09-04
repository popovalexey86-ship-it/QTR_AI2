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

    A valid raid requires price to trade strictly below a mapped level and the
    same closed 5m candle to reclaim strictly above that level. Merely touching
    a level, closing on it, or sweeping buy-side liquidity does not qualify.
    """

    def detect(self, candle: Candle, liquidity_map: LongLiquidityMap) -> LongLiquidityRaid | None:
        candidates = [
            level
            for level in liquidity_map.sell_side
            if candle.low < level.price < candle.close
        ]
        if not candidates:
            return None

        # If one candle raids several mapped lows, anchor the event to the
        # highest reclaimed level: it is the first sell-side pool reclaimed on
        # the bullish return and therefore the most conservative confirmation.
        level = max(candidates, key=lambda item: item.price)
        return LongLiquidityRaid(level=level, candle=candle)
