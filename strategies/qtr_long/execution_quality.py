from dataclasses import dataclass
from enum import Enum

from core.bos_type import BOSType
from core.market_structure_state import MarketStructureState
from strategies.qtr_long.displacement import LongDisplacement


class LongExecutionQualityDecision(Enum):
    ALLOW = "allow"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class LongExecutionQualityResult:
    decision: LongExecutionQualityDecision
    reason: str


class LongExecutionQualityGate:
    """Candidate C filter for structurally conflicting or exhausted 5m impulses.

    This gate is intentionally narrow and LONG-only. It does not create a BUY;
    it may only veto an otherwise valid Candidate B execution sequence.
    """

    def __init__(
        self,
        *,
        max_body_ratio: float = 0.90,
        max_close_location: float = 0.95,
    ) -> None:
        if not 0 < max_body_ratio <= 1:
            raise ValueError("max_body_ratio must be in (0, 1]")
        if not 0 < max_close_location <= 1:
            raise ValueError("max_close_location must be in (0, 1]")
        self._max_body_ratio = max_body_ratio
        self._max_close_location = max_close_location

    def evaluate(
        self,
        *,
        displacement: LongDisplacement,
        state: MarketStructureState | None,
    ) -> LongExecutionQualityResult:
        if state is not None and state.last_bos is not None:
            if state.last_bos.type == BOSType.BEARISH:
                return LongExecutionQualityResult(
                    LongExecutionQualityDecision.BLOCK,
                    "Candidate C blocks LONG while the latest 5m BOS is bearish",
                )

        if displacement.body_ratio > self._max_body_ratio:
            return LongExecutionQualityResult(
                LongExecutionQualityDecision.BLOCK,
                "Candidate C blocks overextended 5m displacement body",
            )

        if displacement.close_location > self._max_close_location:
            return LongExecutionQualityResult(
                LongExecutionQualityDecision.BLOCK,
                "Candidate C blocks 5m displacement closing too near the high",
            )

        return LongExecutionQualityResult(
            LongExecutionQualityDecision.ALLOW,
            "Candidate C 5m execution quality confirmed",
        )
