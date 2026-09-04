from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class FairValueGapDirection(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class FairValueGapStatus(Enum):
    OPEN = "open"
    MITIGATED = "mitigated"
    FILLED = "filled"


@dataclass(frozen=True, slots=True)
class FairValueGap:
    """Three-candle price imbalance used by the QTR SMC layer."""

    index: int
    timestamp: datetime
    direction: FairValueGapDirection
    low: float
    high: float
    status: FairValueGapStatus = FairValueGapStatus.OPEN

    def __post_init__(self) -> None:
        if self.low >= self.high:
            raise ValueError("FVG low must be below high")

    @property
    def midpoint(self) -> float:
        return (self.low + self.high) / 2

    def contains(self, price: float) -> bool:
        return self.low <= price <= self.high
