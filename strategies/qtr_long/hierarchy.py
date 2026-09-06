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
from strategies.qtr_long.execution_quality import (
    LongExecutionQualityDecision,
    LongExecutionQualityGate,
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
    BUY_PLAN = "buy_plan"
    SKIP = "skip"


class LongHierarchyStage(Enum):
    NARRATIVE_4H = "narrative_4h"
    STRUCTURE_1H = "structure_1h"
    POI_15M = "poi_15m"
    LIQUIDITY_MAP_15M = "liquidity_map_15m"
    RAID_5M = "raid_5m"
    DISPLACEMENT_5M = "displacement_5m"
    STRUCTURE_5M = "structure_5m"
    QUALITY_5M = "quality_5m"
    ENTRY_5M = "entry_5m"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class LongHierarchyResult:
    decision: LongHierarchyDecision
    stage: LongHierarchyStage
    reason: str
    entry_plan: LongExecutionEntryPlan | None = None
    details: str | None = None

    def __post_init__(self) -> None:
        if self.decision == LongHierarchyDecision.BUY_PLAN and self.entry_plan is None:
            raise ValueError("BUY_PLAN requires an entry plan")
        if self.decision == LongHierarchyDecision.SKIP and self.entry_plan is not None:
            raise ValueError("SKIP cannot contain an entry plan")


class QTRLongHierarchy:
    """Stateful LONG-only vNext hierarchy.

    Candidate C preserves Candidate B discovery frequency but adds one narrow
    execution-quality hypothesis: do not buy while the latest 5m BOS is bearish
    and do not buy after an overextended bullish displacement.
    """

    def __init__(
        self,
        *,
        max_candles_after_raid: int = 5,
        max_candles_after_displacement: int = 5,
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
        self._quality_gate = LongExecutionQualityGate()
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

        liquidity_map = self._liquidity_map_engine.build(setup_15m.market_structure_state)

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
                    details=self._execution_details(execution_5m),
                )

        if self._structure_shift is None:
            self._structure_shift = self._structure_shift_engine.confirm(
                execution_5m.market_structure_state,
                self._displacement,
                execution_5m.market_data,
            )
            if self._structure_shift is None:
                return self._skip(
                    LongHierarchyStage.STRUCTURE_5M,
                    "waiting for bullish 5m MSS/BOS after displacement",
                    details=self._execution_details(execution_5m),
                )

        quality = self._quality_gate.evaluate(
            displacement=self._displacement,
            state=execution_5m.market_structure_state,
        )
        if quality.decision != LongExecutionQualityDecision.ALLOW:
            details = self._execution_details(execution_5m)
            self._reset_execution()
            return self._skip(
                LongHierarchyStage.QUALITY_5M,
                quality.reason,
                details=details,
            )

        plan = self._entry_engine.build(
            raid=self._raid,
            displacement=self._displacement,
            structure_shift=self._structure_shift,
            fair_value_gap=execution_5m.fair_value_gap,
            order_block=execution_5m.order_block,
        )
        if plan is None:
            details = self._execution_details(execution_5m)
            self._reset_execution()
            return self._skip(
                LongHierarchyStage.ENTRY_5M,
                "confirmed execution sequence has no valid 5m entry zone",
                details=details,
            )

        result = LongHierarchyResult(
            decision=LongHierarchyDecision.BUY_PLAN,
            stage=LongHierarchyStage.READY,
            reason="hierarchical QTR Long Candidate C sequence confirmed",
            entry_plan=plan,
            details=self._execution_details(execution_5m),
        )
        self._reset_execution()
        return result

    def _expire_stale_execution(self, current_index: int) -> None:
        if self._raid is not None and self._displacement is None:
            if current_index > self._raid.candle.index + self._max_candles_after_raid:
                self._reset_execution()
                return

        if self._displacement is not None and self._structure_shift is None:
            if current_index > self._displacement.candle.index + self._max_candles_after_displacement:
                self._reset_execution()

    def _execution_details(self, execution_5m: AnalysisContext) -> str:
        parts = [
            f"current_index={execution_5m.market_data.last.index}",
            f"current_time={execution_5m.market_data.last.timestamp.isoformat()}",
        ]

        if self._raid is not None:
            parts.extend((
                f"raid_index={self._raid.candle.index}",
                f"raid_time={self._raid.candle.timestamp.isoformat()}",
                f"raid_level={self._raid.level.price:.8f}",
                f"raid_extreme={self._raid.extreme_price:.8f}",
                f"raid_reclaim={self._raid.reclaim_close:.8f}",
            ))

        if self._displacement is not None:
            parts.extend((
                f"displacement_index={self._displacement.candle.index}",
                f"displacement_time={self._displacement.candle.timestamp.isoformat()}",
                f"body_ratio={self._displacement.body_ratio:.4f}",
                f"range_expansion={self._displacement.range_expansion:.4f}",
                f"close_location={self._displacement.close_location:.4f}",
            ))

        state = execution_5m.market_structure_state
        if state is None:
            parts.append("structure_state=none")
            return " ".join(parts)

        parts.append(f"trend={state.trend.value}")
        if state.last_choch is None:
            parts.append("last_choch=none")
        else:
            parts.extend((
                f"last_choch={state.last_choch.type.value}",
                f"last_choch_index={state.last_choch.index}",
                f"last_choch_time={state.last_choch.timestamp.isoformat()}",
                f"last_choch_price={state.last_choch.price:.8f}",
            ))
        if state.last_bos is None:
            parts.append("last_bos=none")
        else:
            parts.extend((
                f"last_bos={state.last_bos.type.value}",
                f"last_bos_index={state.last_bos.index}",
                f"last_bos_time={state.last_bos.timestamp.isoformat()}",
                f"last_bos_price={state.last_bos.price:.8f}",
            ))
        return " ".join(parts)

    def _reset_execution(self) -> None:
        self._raid = None
        self._displacement = None
        self._structure_shift = None

    @staticmethod
    def _skip(
        stage: LongHierarchyStage,
        reason: str,
        *,
        details: str | None = None,
    ) -> LongHierarchyResult:
        return LongHierarchyResult(
            decision=LongHierarchyDecision.SKIP,
            stage=stage,
            reason=reason,
            details=details,
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
