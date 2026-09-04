from dataclasses import dataclass
from enum import Enum


class LongNarrativeBias(Enum):
    """Higher-timeframe directional thesis for QTR Long."""

    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"


class LongNarrativeDecision(Enum):
    """Whether QTR Long may continue searching for a BUY setup."""

    ALLOW = "allow"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class LongNarrative:
    """Explicit higher-timeframe narrative snapshot.

    The model is deliberately small at the first vNext milestone. It must be
    populated from synchronized higher-timeframe data later; the current 15m
    AnalysisContext is not silently promoted into an HTF narrative.
    """

    bias: LongNarrativeBias
    source_timeframe: str
    reason: str

    def __post_init__(self) -> None:
        if not self.source_timeframe.strip():
            raise ValueError("source_timeframe must not be empty")
        if not self.reason.strip():
            raise ValueError("reason must not be empty")


class LongNarrativeGate:
    """Mandatory first gate in the QTR Long vNext hierarchy.

    Only an explicit bullish HTF narrative allows the strategy to continue.
    Neutral and bearish narratives produce SKIP downstream. They never create
    SELL/SHORT permission.
    """

    def evaluate(self, narrative: LongNarrative | None) -> LongNarrativeDecision:
        if narrative is None:
            return LongNarrativeDecision.BLOCK

        if narrative.bias == LongNarrativeBias.BULLISH:
            return LongNarrativeDecision.ALLOW

        return LongNarrativeDecision.BLOCK
