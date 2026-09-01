from enum import Enum

from core.analysis_context import AnalysisContext
from core.trend import Trend


class LongMarketRegime(Enum):
    """Whether QTR Long is allowed to continue searching for a buy setup."""

    ALLOWED = "allowed"
    CONDITIONAL = "conditional"
    BLOCKED = "blocked"


class LongRegimeEngine:
    """Classify market context from the perspective of a long-only bot.

    A bearish market blocks new longs. A range is deliberately not treated as
    an automatic rejection: later SMC setup layers may permit edge/sweep/reclaim
    opportunities inside a range.
    """

    def evaluate(self, context: AnalysisContext) -> LongMarketRegime:
        if context.trend == Trend.BEARISH:
            return LongMarketRegime.BLOCKED

        if context.trend == Trend.BULLISH:
            return LongMarketRegime.ALLOWED

        return LongMarketRegime.CONDITIONAL
