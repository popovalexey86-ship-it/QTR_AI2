import math

from core.decision import Decision
from core.setup import Setup
from core.trade_request import TradeRequest


class RiskManager:
    def __init__(
        self,
        risk_reward: float,
        symbol: str,
        volume: float,
    ) -> None:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("RiskManager symbol cannot be empty.")
        if (
            isinstance(volume, bool)
            or not isinstance(volume, (int, float))
            or not math.isfinite(volume)
            or volume <= 0
        ):
            raise ValueError("RiskManager volume must be finite and positive.")
        if (
            isinstance(risk_reward, bool)
            or not isinstance(risk_reward, (int, float))
            or not math.isfinite(risk_reward)
            or risk_reward <= 0
        ):
            raise ValueError(
                "RiskManager risk/reward must be finite and positive."
            )
        self._risk_reward = float(risk_reward)
        self._symbol = normalized_symbol
        self._volume = float(volume)

    def build(
        self,
        setup: Setup,
        decision: Decision,
    ) -> TradeRequest:
        risk = abs(setup.entry - setup.stop_loss)
        if decision == Decision.BUY:
            take_profit = setup.entry + risk * self._risk_reward
        else:
            take_profit = setup.entry - risk * self._risk_reward

        return TradeRequest(
            symbol=self._symbol,
            decision=decision,
            entry=setup.entry,
            stop_loss=setup.stop_loss,
            take_profit=take_profit,
            volume=self._volume,
            setup=setup,
        )
