import math

from core.decision import Decision
from core.setup import Setup
from core.trade_request import TradeRequest


class LongOnlyRiskManager:
    """Execution boundary for QTR Long.

    The generic RiskManager supports both BUY and SELL. QTR Long deliberately
    uses a separate boundary so a SELL request cannot be created even if an
    upstream collaborator is misconfigured.
    """

    def __init__(self, *, risk_reward: float, symbol: str, volume: float) -> None:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol cannot be empty")
        if not math.isfinite(risk_reward) or risk_reward <= 0:
            raise ValueError("risk_reward must be finite and positive")
        if not math.isfinite(volume) or volume <= 0:
            raise ValueError("volume must be finite and positive")

        self._risk_reward = float(risk_reward)
        self._symbol = normalized_symbol
        self._volume = float(volume)

    def build(self, setup: Setup, decision: Decision) -> TradeRequest:
        if decision != Decision.BUY:
            raise ValueError("QTR Long can create BUY requests only")
        if setup.trend.value != "BULLISH":
            raise ValueError("QTR Long requires a bullish setup")
        if setup.entry <= 0 or setup.stop_loss <= 0 or setup.stop_loss >= setup.entry:
            raise ValueError("QTR Long stop loss must be positive and below entry")

        risk = setup.entry - setup.stop_loss
        take_profit = setup.entry + risk * self._risk_reward

        return TradeRequest(
            symbol=self._symbol,
            decision=Decision.BUY,
            entry=setup.entry,
            stop_loss=setup.stop_loss,
            take_profit=take_profit,
            volume=self._volume,
            setup=setup,
        )
