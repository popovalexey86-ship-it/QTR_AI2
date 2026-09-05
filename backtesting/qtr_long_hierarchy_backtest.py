from dataclasses import dataclass
from datetime import datetime

from backtesting.backtest_runner import BacktestInputError
from backtesting.qtr_long_hierarchy_runner import (
    QTRLongHierarchyBacktestResult,
    QTRLongHierarchyBacktestRunner,
)
from backtesting.qtr_long_mtf_analysis import QTRLongMTFAnalysisCoordinator
from backtesting.qtr_long_mtf_historical import QTRLongHistoricalBundle
from backtesting.qtr_long_mtf_snapshots import iter_qtr_long_timeframe_contexts
from core.analysis_engine import AnalysisEngine
from core.bos_engine import BOSEngine
from core.choch_engine import CHOCHEngine
from core.setup_engine import SetupEngine
from core.swing_engine import SwingEngine
from core.trend_engine import TrendEngine
from market_structure.market_structure_engine import MarketStructureEngine
from market_structure.structure_engine import StructureEngine
from strategies.qtr_long.hierarchy import QTRLongHierarchy


@dataclass(frozen=True, slots=True)
class QTRLongHierarchyBacktestConfig:
    symbol: str
    history_window: int = 500
    evaluation_start: datetime | None = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if self.history_window <= 0:
            raise ValueError("history_window must be greater than zero")
        if self.evaluation_start is not None and (
            self.evaluation_start.tzinfo is None
            or self.evaluation_start.utcoffset() is None
        ):
            raise ValueError("evaluation_start must be timezone-aware")


def create_analysis_engine() -> AnalysisEngine:
    """Create one independent stateful analysis engine for exactly one timeframe."""
    return AnalysisEngine(
        swing_engine=SwingEngine(),
        structure_engine=StructureEngine(),
        market_structure_engine=MarketStructureEngine(),
        bos_engine=BOSEngine(),
        choch_engine=CHOCHEngine(),
        trend_engine=TrendEngine(),
        setup_engine=SetupEngine(),
    )


def run_qtr_long_hierarchy_backtest(
    *,
    bundle: QTRLongHistoricalBundle,
    config: QTRLongHierarchyBacktestConfig,
) -> QTRLongHierarchyBacktestResult:
    """Run the decision-level vNext QTR Long hierarchy on one historical bundle.

    Four separate AnalysisEngine instances are mandatory because AnalysisEngine
    owns mutable market-structure, liquidity, order-block and FVG state. The 5m
    execution clock drives synchronization; closed higher-timeframe candles are
    admitted by ``iter_qtr_long_timeframe_contexts`` without lookahead.

    When ``evaluation_start`` is set, earlier synchronized contexts are used only
    to warm up the four analysis engines. Strategy decisions and diagnostics are
    emitted only from the frozen evaluation boundary onward.
    """
    if bundle.symbol != config.symbol:
        raise BacktestInputError(
            "Historical bundle symbol does not match QTR Long backtest config."
        )

    analysis = QTRLongMTFAnalysisCoordinator(
        execution_5m=create_analysis_engine(),
        setup_15m=create_analysis_engine(),
        structure_1h=create_analysis_engine(),
        narrative_4h=create_analysis_engine(),
    )
    runner = QTRLongHierarchyBacktestRunner(
        symbol=config.symbol,
        analysis=analysis,
        hierarchy=QTRLongHierarchy(),
        evaluation_start=config.evaluation_start,
    )
    contexts = iter_qtr_long_timeframe_contexts(
        symbol=config.symbol,
        execution_5m=bundle.execution_5m.candles,
        setup_15m=bundle.setup_15m.candles,
        structure_1h=bundle.structure_1h.candles,
        narrative_4h=bundle.narrative_4h.candles,
        history_window=config.history_window,
    )
    return runner.run(contexts)
