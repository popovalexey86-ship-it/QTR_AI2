from core.liquidity_sweep import LiquiditySweep, LiquiditySweepDirection
from core.market_data import MarketData
from core.market_structure_state import MarketStructureState
from core.structure import Structure


class LiquiditySweepEngine:
    """Detect reclaim-style sweeps of the latest meaningful swing level."""

    def detect(
        self,
        state: MarketStructureState,
        market_data: MarketData,
    ) -> LiquiditySweep | None:
        if len(market_data) == 0:
            return None

        candle = market_data.last
        low_reference = self._latest(state.last_ll, state.last_hl)
        high_reference = self._latest(state.last_hh, state.last_lh)

        if (
            low_reference is not None
            and candle.low < low_reference.price
            and candle.close > low_reference.price
        ):
            return LiquiditySweep(
                index=candle.index,
                timestamp=candle.timestamp,
                direction=LiquiditySweepDirection.BULLISH,
                swept_price=low_reference.price,
                extreme_price=candle.low,
                reclaim_close=candle.close,
            )

        if (
            high_reference is not None
            and candle.high > high_reference.price
            and candle.close < high_reference.price
        ):
            return LiquiditySweep(
                index=candle.index,
                timestamp=candle.timestamp,
                direction=LiquiditySweepDirection.BEARISH,
                swept_price=high_reference.price,
                extreme_price=candle.high,
                reclaim_close=candle.close,
            )

        return None

    @staticmethod
    def _latest(first: Structure | None, second: Structure | None) -> Structure | None:
        candidates = [item for item in (first, second) if item is not None]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.index)
