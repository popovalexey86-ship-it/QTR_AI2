from datetime import datetime

from core.bos import BOS
from core.bos_type import BOSType
from core.market_structure_state import MarketStructureState
from core.trend import Trend
from strategies.qtr_long.structure_confirmation import (
    LongStructureConfirmationGate,
    LongStructureDecision,
)


def test_bullish_1h_trend_confirms_long_search():
    result = LongStructureConfirmationGate().evaluate(trend=Trend.BULLISH)

    assert result.decision == LongStructureDecision.CONFIRMED
    assert "bullish" in result.reason.lower()


def test_bearish_1h_trend_rejects_long_search():
    result = LongStructureConfirmationGate().evaluate(trend=Trend.BEARISH)

    assert result.decision == LongStructureDecision.REJECTED
    assert "bearish" in result.reason.lower()


def test_range_with_bullish_bos_confirms_transition():
    state = MarketStructureState(
        trend=Trend.RANGE,
        last_bos=BOS(
            index=10,
            timestamp=datetime(2025, 1, 1, 10),
            price=101.0,
            type=BOSType.BULLISH,
        ),
    )

    result = LongStructureConfirmationGate().evaluate(
        trend=Trend.RANGE,
        state=state,
    )

    assert result.decision == LongStructureDecision.CONFIRMED


def test_range_with_bearish_bos_is_rejected():
    state = MarketStructureState(
        trend=Trend.RANGE,
        last_bos=BOS(
            index=10,
            timestamp=datetime(2025, 1, 1, 10),
            price=99.0,
            type=BOSType.BEARISH,
        ),
    )

    result = LongStructureConfirmationGate().evaluate(
        trend=Trend.RANGE,
        state=state,
    )

    assert result.decision == LongStructureDecision.REJECTED


def test_range_without_bos_is_rejected():
    result = LongStructureConfirmationGate().evaluate(
        trend=Trend.RANGE,
        state=MarketStructureState(trend=Trend.RANGE),
    )

    assert result.decision == LongStructureDecision.REJECTED


def test_missing_structure_is_rejected():
    result = LongStructureConfirmationGate().evaluate(trend=None)

    assert result.decision == LongStructureDecision.REJECTED
