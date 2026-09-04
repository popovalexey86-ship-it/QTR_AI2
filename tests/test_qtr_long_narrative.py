import pytest

from strategies.qtr_long.narrative import (
    LongNarrative,
    LongNarrativeBias,
    LongNarrativeDecision,
    LongNarrativeGate,
)


def make_narrative(bias: LongNarrativeBias) -> LongNarrative:
    return LongNarrative(
        bias=bias,
        source_timeframe="4h",
        reason="test narrative",
    )


def test_bullish_narrative_allows_long_search():
    assert (
        LongNarrativeGate().evaluate(make_narrative(LongNarrativeBias.BULLISH))
        == LongNarrativeDecision.ALLOW
    )


def test_neutral_narrative_blocks_long_search():
    assert (
        LongNarrativeGate().evaluate(make_narrative(LongNarrativeBias.NEUTRAL))
        == LongNarrativeDecision.BLOCK
    )


def test_bearish_narrative_blocks_long_search():
    assert (
        LongNarrativeGate().evaluate(make_narrative(LongNarrativeBias.BEARISH))
        == LongNarrativeDecision.BLOCK
    )


def test_missing_narrative_blocks_long_search():
    assert LongNarrativeGate().evaluate(None) == LongNarrativeDecision.BLOCK


def test_narrative_requires_source_timeframe():
    with pytest.raises(ValueError, match="source_timeframe"):
        LongNarrative(
            bias=LongNarrativeBias.BULLISH,
            source_timeframe=" ",
            reason="bullish HTF structure",
        )


def test_narrative_requires_reason():
    with pytest.raises(ValueError, match="reason"):
        LongNarrative(
            bias=LongNarrativeBias.BULLISH,
            source_timeframe="4h",
            reason=" ",
        )
