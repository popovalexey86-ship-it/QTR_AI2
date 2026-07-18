from core.decision import Decision
from core.setup import Setup
from core.trend import Trend


class DecisionEngine:

    def decide(
        self,
        setup: Setup | None,
    ) -> Decision:

        if setup is None:
            return Decision.SKIP

        if setup.trend == Trend.BULLISH:
            return Decision.BUY

        if setup.trend == Trend.BEARISH:
            return Decision.SELL

        return Decision.SKIP
