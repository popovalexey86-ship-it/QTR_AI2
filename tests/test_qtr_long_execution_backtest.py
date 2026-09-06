from datetime import UTC, datetime, timedelta

from backtesting.qtr_long_execution_backtest import (
    LongExecutionBacktestConfig,
    LongExecutionOutcome,
    run_qtr_long_execution_backtest,
)
from backtesting.qtr_long_hierarchy_runner import QTRLongHierarchyBacktestResult
from core.candle import Candle
from strategies.qtr_long.execution_entry import (
    LongExecutionEntryPlan,
    LongExecutionZoneSource,
)
from strategies.qtr_long.hierarchy import (
    LongHierarchyDecision,
    LongHierarchyResult,
    LongHierarchyStage,
)


def _candle(index: int, minute: int, low: float, high: float) -> Candle:
    return Candle(
        timestamp=datetime(2026, 1, 1, 12, minute, tzinfo=UTC),
        open=(low + high) / 2,
        high=high,
        low=low,
        close=(low + high) / 2,
        volume=1.0,
        index=index,
    )


def _result(plan: LongExecutionEntryPlan, plan_time: datetime) -> QTRLongHierarchyBacktestResult:
    decision = LongHierarchyResult(
        decision=LongHierarchyDecision.BUY_PLAN,
        stage=LongHierarchyStage.READY,
        reason="test",
        entry_plan=plan,
    )
    return QTRLongHierarchyBacktestResult(
        symbol="BTCUSDT",
        snapshots_processed=1,
        buy_plan_count=1,
        skip_count=0,
        stage_counts={LongHierarchyStage.READY: 1},
        decisions=(decision,),
        buy_plans=(plan,),
        decision_times=(plan_time,),
    )


def _plan() -> LongExecutionEntryPlan:
    return LongExecutionEntryPlan(
        source=LongExecutionZoneSource.FVG,
        zone_low=99.0,
        zone_high=101.0,
        entry=100.0,
        stop_loss=95.0,
    )


def test_limit_starts_on_next_candle_and_wins_at_2r() -> None:
    plan_time = datetime(2026, 1, 1, 12, 5, tzinfo=UTC)
    candles = [
        _candle(0, 0, 94.0, 111.0),  # confirmation candle: must be ignored
        _candle(1, 5, 99.0, 101.0),  # fills at 100
        _candle(2, 10, 100.0, 110.0),  # TP 110
    ]

    result = run_qtr_long_execution_backtest(
        hierarchy_result=_result(_plan(), plan_time),
        execution_candles=candles,
    )

    assert result.filled == 1
    assert result.wins == 1
    assert result.losses == 0
    assert result.net_r == 2.0
    assert result.trades[0].outcome == LongExecutionOutcome.WIN


def test_same_candle_stop_and_target_counts_as_loss() -> None:
    plan_time = datetime(2026, 1, 1, 12, 5, tzinfo=UTC)
    candles = [_candle(1, 5, 94.0, 111.0)]

    result = run_qtr_long_execution_backtest(
        hierarchy_result=_result(_plan(), plan_time),
        execution_candles=candles,
    )

    assert result.losses == 1
    assert result.net_r == -1.0


def test_unfilled_limit_expires_after_ttl() -> None:
    plan_time = datetime(2026, 1, 1, 12, 5, tzinfo=UTC)
    candles = [
        _candle(index, 5 + index * 5, 101.0, 103.0)
        for index in range(2)
    ]

    result = run_qtr_long_execution_backtest(
        hierarchy_result=_result(_plan(), plan_time),
        execution_candles=candles,
        config=LongExecutionBacktestConfig(pending_ttl_candles=2),
    )

    assert result.expired == 1
    assert result.filled == 0
    assert result.trades[0].outcome == LongExecutionOutcome.EXPIRED
