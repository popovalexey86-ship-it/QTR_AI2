from core.decision import Decision
from core.setup import Setup
from core.trade_request import TradeRequest


class RiskManager:

    def __init__(
        self,
        risk_reward: float,
    ):
        self._risk_reward = risk_reward

    def build(
        self,
        setup: Setup,
        decision: Decision,
    ) -> TradeRequest:

        # Пока объём позиции фиксированный.
        volume = 0.01

        risk = abs(setup.entry - setup.stop_loss)

        if decision == Decision.BUY:
            take_profit = (
                setup.entry + risk * self._risk_reward
            )
        else:
            take_profit = (
                setup.entry - risk * self._risk_reward
            )

        return TradeRequest(
            symbol="BTCUSDT",
            decision=decision,
            entry=setup.entry,
            stop_loss=setup.stop_loss,
            take_profit=take_profit,
            volume=volume,
            setup=setup,
        )