from core.analysis_context import AnalysisContext
from core.market_data import MarketData

from core.swing_engine import SwingEngine
from market_structure.structure_engine import StructureEngine
from market_structure.market_structure_engine import MarketStructureEngine
from core.market_structure_state import MarketStructureState
from core.bos_engine import BOSEngine
from core.choch_engine import CHOCHEngine
from core.trend_engine import TrendEngine
from core.liquidity_sweep import LiquiditySweep
from core.liquidity_sweep_engine import LiquiditySweepEngine
from core.order_block import OrderBlock
from core.order_block_engine import OrderBlockEngine
from core.fair_value_gap import FairValueGap, FairValueGapStatus
from core.fair_value_gap_engine import FairValueGapEngine
from core.setup_engine import SetupEngine


class AnalysisEngine:

    def __init__(
        self,
        swing_engine: SwingEngine,
        structure_engine: StructureEngine,
        market_structure_engine: MarketStructureEngine,
        bos_engine: BOSEngine,
        choch_engine: CHOCHEngine,
        trend_engine: TrendEngine,
        setup_engine: SetupEngine,
        order_block_engine: OrderBlockEngine | None = None,
        liquidity_sweep_engine: LiquiditySweepEngine | None = None,
        fair_value_gap_engine: FairValueGapEngine | None = None,
    ):
        self._swing_engine = swing_engine
        self._structure_engine = structure_engine
        self._market_structure_engine = market_structure_engine
        self._bos_engine = bos_engine
        self._choch_engine = choch_engine
        self._trend_engine = trend_engine
        self._setup_engine = setup_engine
        self._order_block_engine = order_block_engine or OrderBlockEngine()
        self._liquidity_sweep_engine = liquidity_sweep_engine or LiquiditySweepEngine()
        self._fair_value_gap_engine = fair_value_gap_engine or FairValueGapEngine()

        self._state = MarketStructureState()

        self._active_liquidity_sweep: LiquiditySweep | None = None
        self._active_order_block: OrderBlock | None = None
        self._active_fair_value_gap: FairValueGap | None = None

    def analyze(self, market_data: MarketData) -> AnalysisContext:
        context = AnalysisContext(market_data=market_data)

        context.swings = self._swing_engine.detect(market_data)
        context.structures = self._structure_engine.detect(context.swings)

        self._market_structure_engine.update(self._state, context.structures)
        context.market_structure_state = self._state

        detected_sweep = self._liquidity_sweep_engine.detect(self._state, market_data)
        if detected_sweep is not None:
            self._active_liquidity_sweep = detected_sweep
        context.liquidity_sweep = self._active_liquidity_sweep

        context.bos = self._bos_engine.detect(self._state, market_data)
        if context.bos is not None:
            self._state.last_bos = context.bos

        context.choch = self._choch_engine.detect(self._state, market_data)
        if context.choch is not None:
            self._state.last_choch = context.choch

        self._trend_engine.update(self._state)
        context.trend = self._state.trend

        detected_order_block = self._order_block_engine.detect(market_data, context.bos)
        if detected_order_block is not None:
            self._active_order_block = detected_order_block
        elif self._active_order_block is not None:
            self._active_order_block = self._order_block_engine.update_status(
                self._active_order_block,
                market_data.last,
            )
        context.order_block = self._active_order_block

        detected_fvg = self._fair_value_gap_engine.detect(market_data)
        if detected_fvg is not None:
            self._active_fair_value_gap = detected_fvg
        elif self._active_fair_value_gap is not None:
            self._active_fair_value_gap = self._fair_value_gap_engine.update_status(
                self._active_fair_value_gap,
                market_data.last,
            )
            if self._active_fair_value_gap.status == FairValueGapStatus.FILLED:
                self._active_fair_value_gap = None
        context.fair_value_gap = self._active_fair_value_gap

        context.setup = self._setup_engine.detect(self._state)
        return context
