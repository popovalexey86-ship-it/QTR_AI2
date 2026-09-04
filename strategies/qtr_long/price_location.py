from dataclasses import dataclass
from enum import Enum

from core.market_data import MarketData


class PriceZone(Enum):
    DISCOUNT = "discount"
    EQUILIBRIUM = "equilibrium"
    PREMIUM = "premium"


@dataclass(frozen=True, slots=True)
class PriceLocation:
    low: float
    high: float
    equilibrium: float
    position: float
    zone: PriceZone


class PriceLocationEngine:
    """Locate current price inside a recent dealing range."""

    def __init__(self, lookback: int = 20, equilibrium_band: float = 0.05):
        if lookback < 2:
            raise ValueError("lookback must be >= 2")
        if not 0 <= equilibrium_band < 0.5:
            raise ValueError("equilibrium_band must be in [0, 0.5)")
        self._lookback = lookback
        self._band = equilibrium_band

    def evaluate(self, market_data: MarketData) -> PriceLocation | None:
        candles = market_data.candles[-self._lookback:]
        if len(candles) < 2:
            return None

        low = min(candle.low for candle in candles)
        high = max(candle.high for candle in candles)
        width = high - low
        if width <= 0:
            return None

        position = (market_data.last.close - low) / width
        equilibrium = (low + high) / 2

        if position < 0.5 - self._band:
            zone = PriceZone.DISCOUNT
        elif position > 0.5 + self._band:
            zone = PriceZone.PREMIUM
        else:
            zone = PriceZone.EQUILIBRIUM

        return PriceLocation(
            low=low,
            high=high,
            equilibrium=equilibrium,
            position=position,
            zone=zone,
        )
