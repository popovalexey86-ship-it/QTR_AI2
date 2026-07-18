from dataclasses import dataclass
from datetime import datetime

from core.trend import Trend


@dataclass(frozen=True, slots=True)
class Setup:
    """
    Найденная торговая возможность.

    Содержит все параметры торговой идеи, рассчитанные
    на этапе анализа рынка.
    """

    index: int
    timestamp: datetime

    trend: Trend

    entry: float
    stop_loss: float
    take_profit: float