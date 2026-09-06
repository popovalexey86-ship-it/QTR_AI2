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
    """4H directional veto for the QTR Long hierarchy.

    The 4H layer is now context rather than a bullish-only permission gate.
    Bullish and neutral narratives may continue to lower-timeframe validation;
    only an explicit bearish narrative vetoes a LONG search. Missing narrative
    still blocks because the hierarchy must not trade without HTF context.

    This remains LONG-only: bearish context never creates SELL/SHORT permission.
    """

    def evaluate(self, narrative: LongNarrative | None) -> LongNarrativeDecision:
        if narrative is None:
            return LongNarrativeDecision.BLOCK

        if narrative.bias == LongNarrativeBias.BEARISH:
            return LongNarrativeDecision.BLOCK

        return LongNarrativeDecision.ALLOW
