from core.decision import Decision
from core.decision_engine import DecisionEngine
from core.setup import Setup
from core.trend import Trend


class LongDecisionEngine(DecisionEngine):
    """Decision gate for QTR Long.

    This engine can only emit BUY or SKIP. A bearish setup is information to
    reject a trade, never permission to open a short position.
    """

    def decide(self, setup: Setup | None) -> Decision:
        if setup is None:
            return Decision.SKIP

        if setup.trend == Trend.BULLISH:
            return Decision.BUY

        return Decision.SKIP
