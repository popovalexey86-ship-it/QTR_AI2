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

        risk = abs(setup.entry - setup.stop_loss)

        if decision == Decision.BUY:
            take_profit = setup.entry + risk * self._risk_reward

        elif decision == Decision.SELL:
            take_profit = setup.entry - risk * self._risk_reward

        else:
            take_profit = setup.entry

        return TradeRequest(
            decision=decision,
            entry=setup.entry,
            stop_loss=setup.stop_loss,
            take_profit=take_profit,
            volume=0.0,
            setup=setup,
        )