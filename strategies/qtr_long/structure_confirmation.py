from dataclasses import dataclass
from enum import Enum

from core.bos_type import BOSType
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
    """Mandatory 1H gate between the 4H narrative and lower-timeframe setup.

    QTR Long requires bullish 1H structure. A RANGE state is accepted only when
    the latest confirmed structural break is bullish, which represents an early
    transition toward bullish structure. Bearish structure can only reject a
    LONG; it never creates SELL/SHORT permission.
    """

    def evaluate(
        self,
        *,
        trend: Trend | None,
        state: MarketStructureState | None = None,
    ) -> LongStructureConfirmation:
        if trend == Trend.BULLISH:
            return LongStructureConfirmation(
                decision=LongStructureDecision.CONFIRMED,
                reason="1H trend is bullish",
            )

        if trend == Trend.RANGE and state is not None and state.last_bos is not None:
            if state.last_bos.type == BOSType.BULLISH:
                return LongStructureConfirmation(
                    decision=LongStructureDecision.CONFIRMED,
                    reason="1H range has a bullish structural break",
                )

        if trend == Trend.BEARISH:
            reason = "1H trend is bearish"
        elif trend == Trend.RANGE:
            reason = "1H range lacks bullish structural confirmation"
        else:
            reason = "1H structure is unavailable"

        return LongStructureConfirmation(
            decision=LongStructureDecision.REJECTED,
            reason=reason,
        )
