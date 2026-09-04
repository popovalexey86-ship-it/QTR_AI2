from dataclasses import dataclass
from enum import Enum


class LongScoreGrade(Enum):
    IGNORE = "ignore"
    WATCH = "watch"
    POSSIBLE = "possible"
    LONG = "long"
    A_PLUS = "a_plus"


@dataclass(frozen=True, slots=True)
class LongScore:
    """Transparent 0-100 score for a QTR Long candidate."""

    structure: int
    liquidity: int
    order_block: int
    fvg: int
    momentum: int
    volume: int
    location: int

    def __post_init__(self) -> None:
        limits = {
            "structure": 25,
            "liquidity": 20,
            "order_block": 15,
            "fvg": 10,
            "momentum": 10,
            "volume": 10,
            "location": 10,
        }
        for name, maximum in limits.items():
            value = getattr(self, name)
            if not 0 <= value <= maximum:
                raise ValueError(f"{name} score must be between 0 and {maximum}")

    @property
    def total(self) -> int:
        return (
            self.structure
            + self.liquidity
            + self.order_block
            + self.fvg
            + self.momentum
            + self.volume
            + self.location
        )

    @property
    def grade(self) -> LongScoreGrade:
        if self.total >= 90:
            return LongScoreGrade.A_PLUS
        if self.total >= 80:
            return LongScoreGrade.LONG
        if self.total >= 70:
            return LongScoreGrade.POSSIBLE
        if self.total >= 60:
            return LongScoreGrade.WATCH
        return LongScoreGrade.IGNORE
