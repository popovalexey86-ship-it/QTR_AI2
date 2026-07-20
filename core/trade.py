from dataclasses import dataclass
from datetime import datetime

from core.decision import Decision


@dataclass(slots=True)
class Trade:
    ticket: str
    symbol: str
    decision: Decision

    entry: float
    exit: float

    volume: float

    pnl: float
    fees: float

    opened_at: datetime
    closed_at: datetime