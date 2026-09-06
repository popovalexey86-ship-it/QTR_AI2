from datetime import UTC, datetime

from core.bos import BOS
from core.bos_type import BOSType
from core.candle import Candle
from core.market_structure_state import MarketStructureState
from strategies.qtr_long.displacement import LongDisplacement
from strategies.qtr_long.execution_quality import (
    LongExecutionQualityDecision,
    LongExecutionQualityGate,
)


NOW = datetime(2026, 9, 6, tzinfo=UTC)


def _displacement(*, body_ratio: float = 0.80, close_location: float = 0.90) -> LongDisplacement:
    return LongDisplacement(
        candle=Candle(
            timestamp=NOW,
            open=100.0,
            high=102.0,
            low=99.0,
            close=101.5,
            volume=1.0,
            index=10,
        ),
        body_ratio=body_ratio,
        range_expansion=1.5,
        close_location=close_location,
    )


def test_allows_candidate_c_quality_at_thresholds() -> None:
    result = LongExecutionQualityGate().evaluate(
        displacement=_displacement(body_ratio=0.90, close_location=0.95),
        state=MarketStructureState(),
    )

    assert result.decision == LongExecutionQualityDecision.ALLOW


def test_blocks_latest_bearish_5m_bos() -> None:
    state = MarketStructureState(
        last_bos=BOS(
            index=9,
            timestamp=NOW,
            price=100.0,
            type=BOSType.BEARISH,
        )
    )
    result = LongExecutionQualityGate().evaluate(
        displacement=_displacement(),
        state=state,
    )

    assert result.decision == LongExecutionQualityDecision.BLOCK
    assert "BOS is bearish" in result.reason


def test_blocks_overextended_displacement_body() -> None:
    result = LongExecutionQualityGate().evaluate(
        displacement=_displacement(body_ratio=0.9001),
        state=MarketStructureState(),
    )

    assert result.decision == LongExecutionQualityDecision.BLOCK
    assert "overextended" in result.reason


def test_blocks_displacement_closing_too_near_high() -> None:
    result = LongExecutionQualityGate().evaluate(
        displacement=_displacement(close_location=0.9501),
        state=MarketStructureState(),
    )

    assert result.decision == LongExecutionQualityDecision.BLOCK
    assert "too near the high" in result.reason
