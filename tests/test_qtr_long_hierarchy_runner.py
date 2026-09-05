from datetime import UTC, datetime, timedelta

import pytest

from backtesting.backtest_runner import BacktestInputError
from backtesting.qtr_long_hierarchy_runner import QTRLongHierarchyBacktestRunner
from backtesting.qtr_long_mtf_analysis import QTRLongMTFAnalysis
from core.analysis_context import AnalysisContext
from core.candle import Candle
from core.market_data import MarketData
from strategies.qtr_long.execution_entry import (
    LongExecutionEntryPlan,
    LongExecutionZoneSource,
)
from strategies.qtr_long.hierarchy import (
    LongHierarchyDecision,
    LongHierarchyResult,
    LongHierarchyStage,
)
from strategies.qtr_long.timeframe_context import QTRLongTimeframeContext


BASE = datetime(2026, 1, 1, tzinfo=UTC)


def _market_data(symbol: str, timeframe: str, timestamp: datetime) -> MarketData:
    candle = Candle(
        timestamp=timestamp,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1.0,
        index=0,
    )
    return MarketData(
        symbol=symbol,
        timeframe=timeframe,
        candles=[candle],
        loaded_at=timestamp,
    )


def _context(*, as_of: datetime, symbol: str = "BTCUSDT") -> QTRLongTimeframeContext:
    return QTRLongTimeframeContext(
        execution_5m=_market_data(symbol, "5", as_of - timedelta(minutes=5)),
        setup_15m=_market_data(symbol, "15", as_of - timedelta(minutes=15)),
        structure_1h=_market_data(symbol, "60", as_of - timedelta(hours=1)),
        narrative_4h=_market_data(symbol, "240", as_of - timedelta(hours=4)),
        as_of=as_of,
    )


def _analysis(context: QTRLongTimeframeContext) -> QTRLongMTFAnalysis:
    return QTRLongMTFAnalysis(
        execution_5m=AnalysisContext(context.execution_5m),
        setup_15m=AnalysisContext(context.setup_15m),
        structure_1h=AnalysisContext(context.structure_1h),
        narrative_4h=AnalysisContext(context.narrative_4h),
    )


class FakeCoordinator:
    def __init__(self) -> None:
        self.calls = 0

    def analyze(self, context: QTRLongTimeframeContext) -> QTRLongMTFAnalysis:
        self.calls += 1
        return _analysis(context)


class FakeHierarchy:
    def __init__(self, results: list[LongHierarchyResult]) -> None:
        self._results = iter(results)
        self.calls = 0

    def evaluate(self, **kwargs) -> LongHierarchyResult:
        self.calls += 1
        return next(self._results)


def _skip(stage: LongHierarchyStage) -> LongHierarchyResult:
    return LongHierarchyResult(
        decision=LongHierarchyDecision.SKIP,
        stage=stage,
        reason="blocked",
    )


def _buy() -> LongHierarchyResult:
    plan = LongExecutionEntryPlan(
        source=LongExecutionZoneSource.FVG,
        zone_low=100.0,
        zone_high=102.0,
        entry=101.0,
        stop_loss=99.0,
    )
    return LongHierarchyResult(
        decision=LongHierarchyDecision.BUY_PLAN,
        stage=LongHierarchyStage.READY,
        reason="ready",
        entry_plan=plan,
    )


def test_collects_buy_plans_and_stage_diagnostics() -> None:
    coordinator = FakeCoordinator()
    hierarchy = FakeHierarchy(
        [
            _skip(LongHierarchyStage.NARRATIVE_4H),
            _skip(LongHierarchyStage.RAID_5M),
            _buy(),
        ]
    )
    runner = QTRLongHierarchyBacktestRunner(
        symbol="BTCUSDT",
        analysis=coordinator,
        hierarchy=hierarchy,
    )
    contexts = [
        _context(as_of=BASE + timedelta(minutes=5 * index))
        for index in (1, 2, 3)
    ]

    result = runner.run(contexts)

    assert result.snapshots_processed == 3
    assert result.buy_plan_count == 1
    assert result.skip_count == 2
    assert len(result.buy_plans) == 1
    assert result.stage_counts[LongHierarchyStage.NARRATIVE_4H] == 1
    assert result.stage_counts[LongHierarchyStage.RAID_5M] == 1
    assert result.stage_counts[LongHierarchyStage.READY] == 1
    assert coordinator.calls == 3
    assert hierarchy.calls == 3


def test_warmup_analysis_runs_before_evaluation_without_counting_decisions() -> None:
    coordinator = FakeCoordinator()
    hierarchy = FakeHierarchy([_skip(LongHierarchyStage.NARRATIVE_4H)])
    evaluation_start = BASE + timedelta(minutes=15)
    runner = QTRLongHierarchyBacktestRunner(
        symbol="BTCUSDT",
        analysis=coordinator,
        hierarchy=hierarchy,
        evaluation_start=evaluation_start,
    )
    contexts = [
        _context(as_of=BASE + timedelta(minutes=5 * index))
        for index in (1, 2, 3)
    ]

    result = runner.run(contexts)

    assert coordinator.calls == 3
    assert hierarchy.calls == 1
    assert result.snapshots_processed == 1
    assert result.skip_count == 1
    assert result.stage_counts[LongHierarchyStage.NARRATIVE_4H] == 1


def test_rejects_empty_input_and_is_single_use() -> None:
    runner = QTRLongHierarchyBacktestRunner(
        symbol="BTCUSDT",
        analysis=FakeCoordinator(),
        hierarchy=FakeHierarchy([]),
    )

    with pytest.raises(BacktestInputError, match="cannot be empty"):
        runner.run([])

    with pytest.raises(RuntimeError, match="only run once"):
        runner.run([])


def test_rejects_evaluation_window_without_synchronized_contexts() -> None:
    runner = QTRLongHierarchyBacktestRunner(
        symbol="BTCUSDT",
        analysis=FakeCoordinator(),
        hierarchy=FakeHierarchy([]),
        evaluation_start=BASE + timedelta(days=1),
    )

    with pytest.raises(BacktestInputError, match="evaluation period"):
        runner.run([_context(as_of=BASE + timedelta(hours=4))])


def test_rejects_wrong_symbol_before_analysis() -> None:
    coordinator = FakeCoordinator()
    runner = QTRLongHierarchyBacktestRunner(
        symbol="BTCUSDT",
        analysis=coordinator,
        hierarchy=FakeHierarchy([]),
    )

    with pytest.raises(BacktestInputError, match="only symbol"):
        runner.run([_context(as_of=BASE, symbol="ETHUSDT")])

    assert coordinator.calls == 0


def test_rejects_duplicate_or_backward_as_of() -> None:
    same_time = BASE + timedelta(hours=4)
    runner = QTRLongHierarchyBacktestRunner(
        symbol="BTCUSDT",
        analysis=FakeCoordinator(),
        hierarchy=FakeHierarchy([_skip(LongHierarchyStage.NARRATIVE_4H)]),
    )

    with pytest.raises(BacktestInputError, match="strictly increasing"):
        runner.run([
            _context(as_of=same_time),
            _context(as_of=same_time),
        ])


def test_rejects_empty_symbol_and_naive_evaluation_start_at_construction() -> None:
    with pytest.raises(BacktestInputError, match="symbol cannot be empty"):
        QTRLongHierarchyBacktestRunner(
            symbol=" ",
            analysis=FakeCoordinator(),
            hierarchy=FakeHierarchy([]),
        )

    with pytest.raises(BacktestInputError, match="timezone-aware"):
        QTRLongHierarchyBacktestRunner(
            symbol="BTCUSDT",
            analysis=FakeCoordinator(),
            hierarchy=FakeHierarchy([]),
            evaluation_start=datetime(2026, 1, 1),
        )
