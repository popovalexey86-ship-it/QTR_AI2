from dataclasses import dataclass

from core.enums.trend import Trend


@dataclass(slots=True, frozen=True)
class TrendAnalysis:
    """
    Результат анализа тренда.
    """

    trend: Trend

    strength: float = 0.0