from core.analysis_context import AnalysisContext
from core.trend import Trend
from strategies.qtr_long.dealing_range import (
    DealingRangeEngine,
    DealingRangeZone,
)
from strategies.qtr_long.narrative import LongNarrative, LongNarrativeBias


class LongNarrativeEngine:
    """Build a conservative 4H narrative from structure and price location.

    QTR Long is allowed to search for BUYs only when higher-timeframe structure
    is bullish and price is not trading in premium/above the confirmed dealing
    range. Bearish structure is always a bearish narrative. Missing/ambiguous
    structure or range information remains neutral rather than being guessed.
    """

    def __init__(self, dealing_range_engine: DealingRangeEngine | None = None) -> None:
        self._dealing_range_engine = dealing_range_engine or DealingRangeEngine()

    def evaluate(self, context: AnalysisContext) -> LongNarrative:
        if context.market_data.timeframe != "240":
            raise ValueError("QTR Long narrative must be evaluated on 4H data")

        if context.trend == Trend.BEARISH:
            return LongNarrative(
                bias=LongNarrativeBias.BEARISH,
                source_timeframe="240",
                reason="4H structure is bearish",
            )

        if context.trend not in (Trend.BULLISH, Trend.BEARISH):
            return LongNarrative(
                bias=LongNarrativeBias.NEUTRAL,
                source_timeframe="240",
                reason="4H structure is not directionally bullish",
            )

        dealing_range = self._dealing_range_engine.build(context.swings)
        if dealing_range is None:
            return LongNarrative(
                bias=LongNarrativeBias.NEUTRAL,
                source_timeframe="240",
                reason="4H confirmed dealing range is unavailable",
            )

        zone = dealing_range.locate(context.market_data.last.close)
        if zone in (DealingRangeZone.DISCOUNT, DealingRangeZone.EQUILIBRIUM):
            return LongNarrative(
                bias=LongNarrativeBias.BULLISH,
                source_timeframe="240",
                reason=f"4H bullish structure with price in {zone.value}",
            )

        return LongNarrative(
            bias=LongNarrativeBias.NEUTRAL,
            source_timeframe="240",
            reason=f"4H bullish structure but price is in {zone.value}",
        )
