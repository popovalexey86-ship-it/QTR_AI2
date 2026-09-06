from dataclasses import dataclass
from statistics import median

from core.candle import Candle
from core.market_data import MarketData
from strategies.qtr_long.execution_raid import LongLiquidityRaid


@dataclass(frozen=True, slots=True)
class LongDisplacement:
    """Bullish 5m displacement after a confirmed sell-side liquidity raid."""

    candle: Candle
    body_ratio: float
    range_expansion: float
    close_location: float


class LongDisplacementEngine:
    """Detect bullish impulse after a 5m liquidity raid.

    Candidate B keeps the same qualitative requirements but widens the timing
    window and lowers the impulse thresholds so moderate but still directional
    expansion can qualify. This remains LONG-only evidence.
    """

    def __init__(
        self,
        *,
        max_candles_after_raid: int = 5,
        lookback: int = 5,
        minimum_body_ratio: float = 0.50,
        minimum_range_expansion: float = 1.00,
        minimum_close_location: float = 0.65,
    ) -> None:
        if max_candles_after_raid < 1:
            raise ValueError("max_candles_after_raid must be >= 1")
        if lookback < 1:
            raise ValueError("lookback must be >= 1")
        if not 0 < minimum_body_ratio <= 1:
            raise ValueError("minimum_body_ratio must be in (0, 1]")
        if minimum_range_expansion <= 0:
            raise ValueError("minimum_range_expansion must be > 0")
        if not 0 < minimum_close_location <= 1:
            raise ValueError("minimum_close_location must be in (0, 1]")

        self._max_candles_after_raid = max_candles_after_raid
        self._lookback = lookback
        self._minimum_body_ratio = minimum_body_ratio
        self._minimum_range_expansion = minimum_range_expansion
        self._minimum_close_location = minimum_close_location

    def detect(
        self,
        market_data: MarketData,
        raid: LongLiquidityRaid,
    ) -> LongDisplacement | None:
        candidates = [
            candle
            for candle in market_data.candles
            if raid.candle.index < candle.index
            <= raid.candle.index + self._max_candles_after_raid
        ]

        for candle in candidates:
            result = self._evaluate_candle(market_data, raid, candle)
            if result is not None:
                return result

        return None

    def _evaluate_candle(
        self,
        market_data: MarketData,
        raid: LongLiquidityRaid,
        candle: Candle,
    ) -> LongDisplacement | None:
        candle_range = candle.high - candle.low
        if candle_range <= 0 or candle.close <= candle.open:
            return None

        body_ratio = (candle.close - candle.open) / candle_range
        if body_ratio < self._minimum_body_ratio:
            return None

        previous_ranges = [
            item.high - item.low
            for item in market_data.candles
            if item.index < candle.index
            and item.index >= candle.index - self._lookback
            and item.high > item.low
        ]
        if not previous_ranges:
            return None

        baseline_range = median(previous_ranges)
        if baseline_range <= 0:
            return None

        range_expansion = candle_range / baseline_range
        if range_expansion < self._minimum_range_expansion:
            return None

        close_location = (candle.close - candle.low) / candle_range
        if close_location < self._minimum_close_location:
            return None

        if candle.close <= raid.reclaim_close:
            return None

        return LongDisplacement(
            candle=candle,
            body_ratio=body_ratio,
            range_expansion=range_expansion,
            close_location=close_location,
        )
