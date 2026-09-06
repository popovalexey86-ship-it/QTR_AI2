from dataclasses import dataclass
from enum import Enum

from core.market_structure_state import MarketStructureState
from core.trend import Trend


class LongStructureDecision(Enum):
    """Whether the 1H structure supports continuing the LONG search."""

    CONFIRMED = "confirmed"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class LongStructureConfirmation:
    """Explicit 1H confirmation result used by the QTR Long hierarchy."""

    decision: LongStructureDecision
    reason: str


class LongStructureConfirmationGate:
    """1H directional safety gate for QTR Long.

    The relaxed candidate keeps only an explicit bearish 1H trend as a hard
    veto. Bullish and range regimes may continue to the lower-timeframe setup,
    where the 15m/5m layers must still provide LONG-specific evidence.

    Bearish structure never creates SELL/SHORT permission.
    """

    def evaluate(
        self,
        *,
        trend: Trend | None,
        state: MarketStructureState | None = None,
    ) -> LongStructureConfirmation:
        del state  # retained in the contract for diagnostics/future ranking

        if trend == Trend.BULLISH:
            return LongStructureConfirmation(
                decision=LongStructureDecision.CONFIRMED,
                reason="1H trend is bullish",
            )

        if trend == Trend.RANGE:
            return LongStructureConfirmation(
                decision=LongStructureDecision.CONFIRMED,
                reason="1H range is permitted for lower-timeframe LONG confirmation",
            )

        if trend == Trend.BEARISH:
            reason = "1H trend is bearish"
        else:
            reason = "1H structure is unavailable"

        return LongStructureConfirmation(
            decision=LongStructureDecision.REJECTED,
            reason=reason,
        )
