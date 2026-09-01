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

        # Состояние рынка хранится между вызовами analyze()
        self._state = MarketStructureState()

        # Последние SMC-события живут между циклами анализа.
        self._active_liquidity_sweep: LiquiditySweep | None = None
        self._active_order_block: OrderBlock | None = None

    def analyze(
        self,
        market_data: MarketData,
    ) -> AnalysisContext:

        context = AnalysisContext(
            market_data=market_data,
        )

        #
        # 1. Swing
        #
        context.swings = self._swing_engine.detect(
            market_data,
        )

        #
        # 2. Structure
        #
        context.structures = self._structure_engine.detect(
            context.swings,
        )

        #
        # 3. Market Structure State
        #
        self._market_structure_engine.update(
            self._state,
            context.structures,
        )

        context.market_structure_state = self._state

        #
        # 4. SMC Liquidity Sweep
        #
        detected_sweep = self._liquidity_sweep_engine.detect(
            self._state,
            market_data,
        )
        if detected_sweep is not None:
            self._active_liquidity_sweep = detected_sweep
        context.liquidity_sweep = self._active_liquidity_sweep

        #
        # 5. BOS
        #
        context.bos = self._bos_engine.detect(
            self._state,
            market_data,
        )
        if context.bos is not None:
            self._state.last_bos = context.bos

        #
        # 6. CHOCH
        #
        context.choch = self._choch_engine.detect(
            self._state,
            market_data,
        )
        if context.choch is not None:
            self._state.last_choch = context.choch

        #
        # 7. Trend
        #
        self._trend_engine.update(
            self._state,
        )
        context.trend = self._state.trend

        #
        # 8. SMC Order Block
        #
        detected_order_block = self._order_block_engine.detect(
            market_data,
            context.bos,
        )

        if detected_order_block is not None:
            self._active_order_block = detected_order_block
        elif self._active_order_block is not None:
            self._active_order_block = self._order_block_engine.update_status(
                self._active_order_block,
                market_data.last,
            )

        context.order_block = self._active_order_block

        #
        # 9. Setup
        #
        context.setup = self._setup_engine.detect(
            self._state,
        )

        return context
