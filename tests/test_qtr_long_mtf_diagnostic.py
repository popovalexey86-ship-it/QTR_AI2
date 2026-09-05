from datetime import UTC, datetime

import pytest

from backtesting.qtr_long_hierarchy_runner import QTRLongHierarchyBacktestResult
from backtesting.qtr_long_mtf_diagnostic import _parse_utc, format_diagnostic_report
from strategies.qtr_long.hierarchy import (
    LongHierarchyDecision,
    LongHierarchyResult,
    LongHierarchyStage,
)


def _result() -> QTRLongHierarchyBacktestResult:
    skip = LongHierarchyResult(
        decision=LongHierarchyDecision.SKIP,
        stage=LongHierarchyStage.NARRATIVE_4H,
        reason="blocked",
    )
    return QTRLongHierarchyBacktestResult(
        symbol="BTCUSDT",
        snapshots_processed=1,
        buy_plan_count=0,
        skip_count=1,
        stage_counts={LongHierarchyStage.NARRATIVE_4H: 1},
        decisions=(skip,),
        buy_plans=(),
    )


def test_parse_utc_accepts_z_and_rejects_naive_datetime() -> None:
    assert _parse_utc("2025-01-01T00:00:00Z") == datetime(2025, 1, 1, tzinfo=UTC)

    with pytest.raises(Exception, match="timezone-aware UTC"):
        _parse_utc("2025-01-01T00:00:00")


def test_formats_stage_diagnostic_report() -> None:
    report = format_diagnostic_report(
        result=_result(),
        data_start=datetime(2024, 10, 1, tzinfo=UTC),
        evaluation_start=datetime(2025, 1, 1, tzinfo=UTC),
        end=datetime(2025, 2, 1, tzinfo=UTC),
    )

    assert "QTR LONG vNext — MTF DIAGNOSTIC" in report
    assert "Snapshots processed: 1" in report
    assert "BUY_PLAN: 0" in report
    assert "SKIP: 1" in report
    assert "narrative_4h: 1" in report
    assert "ready: 0" in report


def test_formats_timestamped_deep_candidates() -> None:
    as_of = datetime(2025, 1, 17, 12, 35, tzinfo=UTC)
    deep_skip = LongHierarchyResult(
        decision=LongHierarchyDecision.SKIP,
        stage=LongHierarchyStage.STRUCTURE_5M,
        reason="waiting for bullish 5m MSS/BOS after displacement",
    )
    result = QTRLongHierarchyBacktestResult(
        symbol="BTCUSDT",
        snapshots_processed=1,
        buy_plan_count=0,
        skip_count=1,
        stage_counts={LongHierarchyStage.STRUCTURE_5M: 1},
        decisions=(deep_skip,),
        buy_plans=(),
        decision_times=(as_of,),
    )

    report = format_diagnostic_report(
        result=result,
        data_start=datetime(2024, 10, 1, tzinfo=UTC),
        evaluation_start=datetime(2025, 1, 1, tzinfo=UTC),
        end=datetime(2025, 2, 1, tzinfo=UTC),
    )

    assert "Deep candidates:" in report
    assert "as_of=2025-01-17T12:35:00+00:00" in report
    assert "stage=structure_5m" in report
    assert "waiting for bullish 5m MSS/BOS after displacement" in report


def test_rejects_misaligned_decision_times() -> None:
    with pytest.raises(ValueError, match="decision_times must align"):
        QTRLongHierarchyBacktestResult(
            symbol="BTCUSDT",
            snapshots_processed=1,
            buy_plan_count=0,
            skip_count=1,
            stage_counts={LongHierarchyStage.NARRATIVE_4H: 1},
            decisions=_result().decisions,
            buy_plans=(),
            decision_times=(
                datetime(2025, 1, 1, tzinfo=UTC),
                datetime(2025, 1, 2, tzinfo=UTC),
            ),
        )
