from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from backtesting.backtest_runner import BacktestInputError
from backtesting.qtr_long_mtf_analysis import QTRLongMTFAnalysis
from strategies.qtr_long.execution_entry import LongExecutionEntryPlan
from strategies.qtr_long.hierarchy import (
    LongHierarchyDecision,
    LongHierarchyResult,
    LongHierarchyStage,
)
from strategies.qtr_long.timeframe_context import QTRLongTimeframeContext


class MTFAnalysisCoordinator(Protocol):
    """Analysis coordinator contract consumed by the hierarchy backtest runner."""

    def analyze(self, context: QTRLongTimeframeContext) -> QTRLongMTFAnalysis:
        ...


class LongHierarchyEvaluator(Protocol):
    """LONG-only hierarchy contract consumed by the backtest runner."""

    def evaluate(
        self,
        *,
        timeframe_context: QTRLongTimeframeContext,
        narrative_4h,
        structure_1h,
        setup_15m,
        execution_5m,
    ) -> LongHierarchyResult:
        ...


@dataclass(frozen=True, slots=True)
class QTRLongHierarchyBacktestResult:
    """Decision-level result before broker/risk execution is introduced."""

    symbol: str
    snapshots_processed: int
    buy_plan_count: int
    skip_count: int
    stage_counts: Mapping[LongHierarchyStage, int]
    decisions: tuple[LongHierarchyResult, ...]
    buy_plans: tuple[LongExecutionEntryPlan, ...]


class QTRLongHierarchyBacktestRunner:
    """Run the vNext hierarchy over synchronized historical MTF contexts.

    This runner deliberately stops at BUY_PLAN / SKIP. It does not simulate
    fills, stops or targets yet. The purpose of this layer is to validate the
    multi-timeframe decision pipeline and collect stage diagnostics without
    silently coupling the new hierarchy to the legacy Genesis risk model.
    """

    def __init__(
        self,
        *,
        symbol: str,
        analysis: MTFAnalysisCoordinator,
        hierarchy: LongHierarchyEvaluator,
    ) -> None:
        if not symbol.strip():
            raise BacktestInputError("Backtest symbol cannot be empty.")
        self._symbol = symbol
        self._analysis = analysis
        self._hierarchy = hierarchy
        self._has_run = False

    def run(
        self,
        contexts: Iterable[QTRLongTimeframeContext],
    ) -> QTRLongHierarchyBacktestResult:
        if self._has_run:
            raise RuntimeError("A QTRLongHierarchyBacktestRunner instance can only run once.")
        self._has_run = True

        decisions: list[LongHierarchyResult] = []
        buy_plans: list[LongExecutionEntryPlan] = []
        stage_counts: Counter[LongHierarchyStage] = Counter()
        previous_as_of: datetime | None = None

        for position, context in enumerate(contexts, start=1):
            self._validate_context(
                context,
                position=position,
                previous_as_of=previous_as_of,
            )
            previous_as_of = context.as_of

            analysis = self._analysis.analyze(context)
            result = self._hierarchy.evaluate(
                timeframe_context=context,
                narrative_4h=analysis.narrative_4h,
                structure_1h=analysis.structure_1h,
                setup_15m=analysis.setup_15m,
                execution_5m=analysis.execution_5m,
            )
            decisions.append(result)
            stage_counts[result.stage] += 1

            if result.decision == LongHierarchyDecision.BUY_PLAN:
                if result.entry_plan is None:
                    raise RuntimeError("Hierarchy returned BUY_PLAN without an entry plan.")
                buy_plans.append(result.entry_plan)

        if not decisions:
            raise BacktestInputError("Historical QTR Long timeframe contexts cannot be empty.")

        buy_plan_count = len(buy_plans)
        return QTRLongHierarchyBacktestResult(
            symbol=self._symbol,
            snapshots_processed=len(decisions),
            buy_plan_count=buy_plan_count,
            skip_count=len(decisions) - buy_plan_count,
            stage_counts=dict(stage_counts),
            decisions=tuple(decisions),
            buy_plans=tuple(buy_plans),
        )

    def _validate_context(
        self,
        context: QTRLongTimeframeContext,
        *,
        position: int,
        previous_as_of: datetime | None,
    ) -> None:
        layers = (
            context.execution_5m,
            context.setup_15m,
            context.structure_1h,
            context.narrative_4h,
        )
        if any(layer.symbol != self._symbol for layer in layers):
            raise BacktestInputError(
                f"MTF context {position} must contain only symbol {self._symbol!r}."
            )
        if previous_as_of is not None and context.as_of <= previous_as_of:
            raise BacktestInputError(
                "Historical QTR Long contexts must have strictly increasing as_of times."
            )
