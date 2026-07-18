from dataclasses import dataclass
from datetime import datetime

from core.decision import Decision


@dataclass(slots=True)
class Position:
    """
    Открытая торговая позиция.
    """

    ticket: int

    decision: Decision

    entry: float

    stop_loss: float

    take_profit: float

    volume: float

    opened_at: datetime

    symbol: str = "BTCUSDT"