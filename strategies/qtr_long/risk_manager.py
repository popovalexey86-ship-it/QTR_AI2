from core.decision import Decision
from core.risk_manager import RiskManager
from core.setup import Setup
from core.trade_request import TradeRequest


class LongOnlyRiskManager(RiskManager):
    """Execution boundary for QTR Long.

    The generic RiskManager supports both BUY and SELL. QTR Long deliberately
    uses a stricter subclass so it remains compatible with the shared trading
    engine while making SELL request creation impossible.
    """

    def build(self, setup: Setup, decision: Decision) -> TradeRequest:
        if decision != Decision.BUY:
            raise ValueError("QTR Long can create BUY requests only")
        if setup.trend.value != "BULLISH":
            raise ValueError("QTR Long requires a bullish setup")
        if setup.entry <= 0 or setup.stop_loss <= 0 or setup.stop_loss >= setup.entry:
            raise ValueError("QTR Long stop loss must be positive and below entry")

        request = super().build(setup, Decision.BUY)
        if request.decision != Decision.BUY:
            raise RuntimeError("QTR Long invariant violated: non-BUY request created")
        return request
