from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class LiquiditySweepDirection(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


@dataclass(frozen=True, slots=True)
class LiquiditySweep:
    """SMC liquidity sweep followed by a close back through the swept level."""

    index: int
    timestamp: datetime
    direction: LiquiditySweepDirection
    swept_price: float
    extreme_price: float
    reclaim_close: float

    def __post_init__(self) -> None:
        if self.direction == LiquiditySweepDirection.BULLISH:
            if self.extreme_price >= self.swept_price:
                raise ValueError("bullish sweep extreme must be below swept price")
            if self.reclaim_close <= self.swept_price:
                raise ValueError("bullish sweep must close back above swept price")
        else:
            if self.extreme_price <= self.swept_price:
                raise ValueError("bearish sweep extreme must be above swept price")
            if self.reclaim_close >= self.swept_price:
                raise ValueError("bearish sweep must close back below swept price")
