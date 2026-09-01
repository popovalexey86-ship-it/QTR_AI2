from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum


class OrderBlockDirection(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class OrderBlockStatus(Enum):
    FRESH = "fresh"
    MITIGATED = "mitigated"
    INVALIDATED = "invalidated"


@dataclass(frozen=True, slots=True)
class OrderBlock:
    """SMC order-block price zone.

    The zone is immutable. State transitions return a new instance so the
    analysis pipeline can keep historical snapshots safely.
    """

    index: int
    timestamp: datetime
    direction: OrderBlockDirection
    low: float
    high: float
    status: OrderBlockStatus = OrderBlockStatus.FRESH

    def __post_init__(self) -> None:
        if self.low > self.high:
            raise ValueError("order block low must be <= high")

    @property
    def midpoint(self) -> float:
        return (self.low + self.high) / 2.0

    def contains(self, price: float) -> bool:
        return self.low <= price <= self.high

    def with_status(self, status: OrderBlockStatus) -> "OrderBlock":
        return replace(self, status=status)
