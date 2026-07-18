from enum import Enum


class Trend(Enum):
    """
    Глобальное направление рынка.
    """

    BULLISH = "BULLISH"

    BEARISH = "BEARISH"

    RANGE = "RANGE"