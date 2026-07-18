from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class Candle:
    """
    Базовая модель свечи.

    Используется всеми модулями системы.
    """

    timestamp: datetime

    open: float
    high: float
    low: float
    close: float

    volume: float
