from dataclasses import dataclass

from core.decision import Decision
from core.setup import Setup


@dataclass(frozen=True, slots=True)
class TradeRequest:
    """
    Готовый запрос на открытие позиции.
    """

    decision: Decision

    entry: float
    stop_loss: float
    take_profit: float

    volume: float

    setup: Setup

    symbol: str = "BTCUSDT"

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("Symbol cannot be empty.")

        if self.volume <= 0:
            raise ValueError("Volume must be greater than zero.")

        if self.decision == Decision.SKIP:
            raise ValueError("TradeRequest cannot be created with Decision.SKIP.")
