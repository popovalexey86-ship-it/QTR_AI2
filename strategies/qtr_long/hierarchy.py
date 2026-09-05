from dataclasses import dataclass
from enum import Enum

from core.analysis_context import AnalysisContext
from core.market_data import MarketData
from strategies.qtr_long.dealing_range import DealingRangeEngine
from strategies.qtr_long.displacement import LongDisplacement, LongDisplacementEngine
from strategies.qtr_long.execution_entry import (
    LongExecutionEntryEngine,
    LongExecutionEntryPlan,
)
from strategies.qtr_long.execution_raid import LongLiquidityRaid, LongLiquidityRaidDetector
from strategies.qtr_long.execution_structure import (
    LongStructureShift,
    LongStructureShiftEngine,
)
from strategies.qtr_long.liquidity_map import LongLiquidityMapEngine
from strategies.qtr_long.narrative import LongNarrativeDecision, LongNarrativeGate
from strategies.qtr_long.narrative_engine import LongNarrativeEngine
from strategies.qtr_long.poi import LongPOIDecision, LongPOIEngine
from strategies.qtr_long.structure_confirmation import (
    LongStructureConfirmationGate,
    LongStructureDecision,
)
from strategies.qtr_long.timeframe_context import QTRLongTimeframeContext


class LongHierarchyDecision(Enum):
    """Terminal decision emitted by the vNext QTR Long hierarchy."""

    BUY_PLAN = "buy_plan"
    SKIP = "skip"


class LongHierarchyStage(Enum):
    """Gate that produced the current hierarchical result."""

    NARRATIVE_4H = "narrative_4h"
    STRUCTURE_1H = "structure_1h"
    POI_15M = "poi_15m"
    LIQUIDITY_MAP_15M = "liquidity_map_15m"
    RAID_5M = "raid_5m"
    DISPLACEMENT_5M = "displacement_5m"
    STRUCTURE_5M = "structure_5m"
    ENTRY_5M = "entry_5m"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class LongHierarchyResult:
    """One hierarchical QTR Long evaluation result.

    A result is either a pending BUY plan or an explicit SKIP with the gate that
    stopped the sequence. SELL/SHORT is intentionally absent from the domain.
    """

    decision: LongHierarchyDecision
    stage: LongHierarchyStage
    reason: str
    entry_plan: LongExecutionEntryPlan | None = None

    def __post_init__(self) -> None:
        if self.decision == LongHierarchyDecision.BUY_PLAN and self.entry_plan is None:
            raise ValueError("BUY_PLAN requires an entry plan")
        if self.decision == LongHierarchyDecision.SKIP and self.entry_plan is not None:
            raise ValueError("SKIP cannot contain an entry plan")


class QTRLongHierarchy:
    """Stateful, LONG-only orchestration of the vNext SMC hierarchy.

    The hierarchy is evaluated from top to bottom on synchronized closed-candle
    analysis contexts:

        4H narrative
        -> 1H structure confirmation + structural dealing range
        -> 15m POI inside the 1H dealing range
        -> 15m sell-side liquidity map
        -> 5m liquidity raid
        -> 5m displacement
        -> 5m bullish MSS/BOS
        -> 5m execution FVG/OB
        -> pending BUY plan

    The 1H layer owns the structural dealing range. The 15m layer supplies the
    candidate bullish POI and liquidity map; it does not redefine the higher-
    timeframe range used for location permission.

    Execution evidence is stateful across successive 5m snapshots. A liquidity
    raid is recorded only when it happens on the current terminal 5m candle;
    the pipeline never scans old candles with a newer 15m liquidity map. This is
    important because doing so could retroactively introduce look-ahead bias.

    Any failed mandatory higher-timeframe gate clears the active 5m sequence.
    The only terminal actions are BUY_PLAN and SKIP.
    """

    def __init__(
        self,
        *,
        max_candles_after_raid: int = 3,
        max_candles_after_displacement: int = 3,
    ) -> None:
        if max_candles_after_raid < 1:
            raise ValueError("max_candles_after_raid must be >= 1")
        if max_candles_after_displacement < 0:
            raise ValueError("max_candles_after_displacement must be >= 0")

        self._max_candles_after_raid = max_candles_after_raid
        self._max_candles_after_displacement = max_candles_after_displacement

        self._narrative_engine = LongNarrativeEngine()
        self._narrative_gate = LongNarrativeGate()
        self._structure_gate = LongStructureConfirmationGate()
        self._dealing_range_engine = DealingRangeEngine()
        self._poi_engine = LongPOIEngine()
        self._liquidity_map_engine = LongLiquidityMapEngine()
        self._raid_detector = LongLiquidityRaidDetector()
        self._displacement_engine = LongDisplacementEngine(
            max_candles_after_raid=max_candles_after_raid,
        )
        self._structure_shift_engine = LongStructureShiftEngine(
            max_candles_after_displacement=max_candles_after_displacement,
        )
        self._entry_engine = LongExecutionEntryEngine()

        self._active_symbol: str | None = None
        self._raid: LongLiquidityRaid | None = None
        self._displacement: LongDisplacement | None = None
        self._structure_shift: LongStructureShift | None = None

    def evaluate(
        self,
        *,
        timeframe_context: QTRLongTimeframeContext,
        narrative_4h: AnalysisContext,
        structure_1h: AnalysisContext,
        setup_15m: AnalysisContext,
        execution_5m: AnalysisContext,
    ) -> LongHierarchyResult:
        self._validate_bindings(
            timeframe_context=timeframe_context,
            narrative_4h=narrative_4h,
            structure_1h=structure_1h,
            setup_15m=setup_15m,
            execution_5m=execution_5m,
        )

        symbol = timeframe_context.execution_5m.symbol
        if self._active_symbol != symbol:
            self._reset_execution()
            self._active_symbol = symbol

        narrative = self._narrative_engine.evaluate(narrative_4h)
        if self._narrative_gate.evaluate(narrative) != LongNarrativeDecision.ALLOW:
            self._reset_execution()
            return self._skip(LongHierarchyStage.NARRATIVE_4H, narrative.reason)

        structure = self._structure_gate.evaluate(
            trend=structure_1h.trend,
            state=structure_1h.market_structure_state,
        )
        if structure.decision != LongStructureDecision.CONFIRMED:
            self._reset_execution()
            return self._skip(LongHierarchyStage.STRUCTURE_1H, structure.reason)

        dealing_range = self._dealing_range_engine.build(structure_1h.swings)
        poi = self._poi_engine.evaluate(
            dealing_range=dealing_range,
            order_block=setup_15m.order_block,
            fair_value_gap=setup_15m.fair_value_gap,
        )
        if poi.decision != LongPOIDecision.ALLOW:
            self._reset_execution()
            return self._skip(LongHierarchyStage.POI_15M, poi.reason)

        current_index = execution_5m.market_data.last.index
        self._expire_stale_execution(current_index)

        liquidity_map = self._liquidity_map_engine.build(
            setup_15m.market_structure_state,
        )

        if self._raid is None:
            if not liquidity_map.has_sell_side_liquidity:
                return self._skip(
                    LongHierarchyStage.LIQUIDITY_MAP_15M,
                    "15m sell-side liquidity map is empty",
                )

            self._raid = self._raid_detector.detect(
                execution_5m.market_data.last,
                liquidity_map,
            )
            if self._raid is None:
                return self._skip(
                    LongHierarchyStage.RAID_5M,
                    "waiting for 5m sell-side liquidity raid",
                )

        if self._displacement is None:
            self._displacement = self._displacement_engine.detect(
                execution_5m.market_data,
                self._raid,
            )
            if self._displacement is None:
                return self._skip(
                    LongHierarchyStage.DISPLACEMENT_5M,
                    "waiting for bullish 5m displacement after raid",
                )

        if self._structure_shift is None:
            self._structure_shift = self._structure_shift_engine.confirm(
                execution_5m.market_structure_state,
                self._displacement,
            )
            if self._structure_shift is None:
                return self._skip(
                    LongHierarchyStage.STRUCTURE_5M,
                    "waiting for bullish 5m MSS/BOS after displacement",
                )

        plan = self._entry_engine.build(
            raid=self._raid,
            displacement=self._displacement,
            structure_shift=self._structure_shift,
            fair_value_gap=execution_5m.fair_value_gap,
            order_block=execution_5m.order_block,
        )
        if plan is None:
            self._reset_execution()
            return self._skip(
                LongHierarchyStage.ENTRY_5M,
                "confirmed execution sequence has no valid 5m entry zone",
            )

        result = LongHierarchyResult(
            decision=LongHierarchyDecision.BUY_PLAN,
            stage=LongHierarchyStage.READY,
            reason="hierarchical QTR Long sequence confirmed",
            entry_plan=plan,
        )
        self._reset_execution()
        return result

    def _expire_stale_execution(self, current_index: int) -> None:
        if self._raid is not None and self._displacement is None:
            if current_index > self._raid.candle.index + self._max_candles_after_raid:
                self._reset_execution()
                return

        if self._displacement is not None and self._structure_shift is None:
            if (
                current_index
                > self._displacement.candle.index + self._max_candles_after_displacement
            ):
                self._reset_execution()

    def _reset_execution(self) -> None:
        self._raid = None
        self._displacement = None
        self._structure_shift = None

    @staticmethod
    def _skip(stage: LongHierarchyStage, reason: str) -> LongHierarchyResult:
        return LongHierarchyResult(
            decision=LongHierarchyDecision.SKIP,
            stage=stage,
            reason=reason,
        )

    @classmethod
    def _validate_bindings(
        cls,
        *,
        timeframe_context: QTRLongTimeframeContext,
        narrative_4h: AnalysisContext,
        structure_1h: AnalysisContext,
        setup_15m: AnalysisContext,
        execution_5m: AnalysisContext,
    ) -> None:
        bindings = (
            ("narrative_4h", narrative_4h.market_data, timeframe_context.narrative_4h),
            ("structure_1h", structure_1h.market_data, timeframe_context.structure_1h),
            ("setup_15m", setup_15m.market_data, timeframe_context.setup_15m),
            ("execution_5m", execution_5m.market_data, timeframe_context.execution_5m),
        )
        for name, analyzed, synchronized in bindings:
            if not cls._same_market_data_snapshot(analyzed, synchronized):
                raise ValueError(
                    f"{name} analysis is not bound to the synchronized timeframe context"
                )

    @staticmethod
    def _same_market_data_snapshot(first: MarketData, second: MarketData) -> bool:
        return (
            first.symbol == second.symbol
            and first.timeframe == second.timeframe
            and len(first) == len(second)
            and first.last == second.last
        )
