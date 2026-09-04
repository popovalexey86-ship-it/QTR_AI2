from dataclasses import replace

from core.candle import Candle
from core.fair_value_gap import (
    FairValueGap,
    FairValueGapDirection,
    FairValueGapStatus,
)
from core.market_data import MarketData


class FairValueGapEngine:
    """Detect and maintain classic three-candle Fair Value Gaps."""

    def detect(self, market_data: MarketData) -> FairValueGap | None:
        if len(market_data.candles) < 3:
            return None

        first, _, third = market_data.candles[-3:]

        if third.low > first.high:
            return FairValueGap(
                index=third.index,
                timestamp=third.timestamp,
                direction=FairValueGapDirection.BULLISH,
                low=first.high,
                high=third.low,
            )

        if third.high < first.low:
            return FairValueGap(
                index=third.index,
                timestamp=third.timestamp,
                direction=FairValueGapDirection.BEARISH,
                low=third.high,
                high=first.low,
            )

        return None

    def update_status(self, gap: FairValueGap, candle: Candle) -> FairValueGap:
        if gap.status == FairValueGapStatus.FILLED:
            return gap

        if gap.direction == FairValueGapDirection.BULLISH:
            if candle.low <= gap.low:
                return replace(gap, status=FairValueGapStatus.FILLED)
            if candle.low < gap.high:
                return replace(gap, status=FairValueGapStatus.MITIGATED)
            return gap

        if candle.high >= gap.high:
            return replace(gap, status=FairValueGapStatus.FILLED)
        if candle.high > gap.low:
            return replace(gap, status=FairValueGapStatus.MITIGATED)
        return gap
