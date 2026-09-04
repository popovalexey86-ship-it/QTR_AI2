from dataclasses import dataclass
from enum import Enum

from core.swing import Swing
from core.swing_type import SwingType


class DealingRangeZone(Enum):
    """Location of price relative to a confirmed HTF dealing range."""

    BELOW_RANGE = "below_range"
    DISCOUNT = "discount"
    EQUILIBRIUM = "equilibrium"
    PREMIUM = "premium"
    ABOVE_RANGE = "above_range"


@dataclass(frozen=True, slots=True)
class DealingRange:
    """Range anchored by confirmed opposite-side HTF swings."""

    low_swing: Swing
    high_swing: Swing
    equilibrium: float

    def __post_init__(self) -> None:
        if self.low_swing.type != SwingType.LOW:
            raise ValueError("low_swing must be a confirmed LOW")
        if self.high_swing.type != SwingType.HIGH:
            raise ValueError("high_swing must be a confirmed HIGH")
        if self.low_swing.price >= self.high_swing.price:
            raise ValueError("dealing range low must be below high")

    @property
    def low(self) -> float:
        return self.low_swing.price

    @property
    def high(self) -> float:
        return self.high_swing.price

    @property
    def width(self) -> float:
        return self.high - self.low

    def position(self, price: float) -> float:
        return (price - self.low) / self.width

    def locate(self, price: float, *, equilibrium_band: float = 0.05) -> DealingRangeZone:
        if not 0 <= equilibrium_band < 0.5:
            raise ValueError("equilibrium_band must be in [0, 0.5)")
        if price < self.low:
            return DealingRangeZone.BELOW_RANGE
        if price > self.high:
            return DealingRangeZone.ABOVE_RANGE

        normalized = self.position(price)
        if normalized < 0.5 - equilibrium_band:
            return DealingRangeZone.DISCOUNT
        if normalized > 0.5 + equilibrium_band:
            return DealingRangeZone.PREMIUM
        return DealingRangeZone.EQUILIBRIUM


class DealingRangeEngine:
    """Build the current HTF dealing range from confirmed swings only.

    This first structural contract deliberately avoids rolling candle highs/lows.
    It uses the most recently confirmed HIGH and LOW supplied by the swing layer.
    Later narrative logic decides whether that range is suitable for a LONG.
    """

    def build(self, swings: list[Swing]) -> DealingRange | None:
        latest_low = next(
            (swing for swing in reversed(swings) if swing.type == SwingType.LOW),
            None,
        )
        latest_high = next(
            (swing for swing in reversed(swings) if swing.type == SwingType.HIGH),
            None,
        )
        if latest_low is None or latest_high is None:
            return None
        if latest_low.price >= latest_high.price:
            return None

        return DealingRange(
            low_swing=latest_low,
            high_swing=latest_high,
            equilibrium=(latest_low.price + latest_high.price) / 2,
        )
