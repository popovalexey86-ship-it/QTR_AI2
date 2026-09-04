from backtesting.backtest_runner import BacktestRunner
from core.analysis_engine import AnalysisEngine
from core.bos_engine import BOSEngine
from core.choch_engine import CHOCHEngine
from core.setup_engine import SetupEngine
from core.swing_engine import SwingEngine
from core.trend_engine import TrendEngine
from market_structure.market_structure_engine import MarketStructureEngine
from market_structure.structure_engine import StructureEngine
from strategies.qtr_long.decision_engine import LongDecisionEngine
from strategies.qtr_long.risk_manager import LongOnlyRiskManager
from strategies.qtr_long.strategy import QTRLongStrategy


def create_qtr_long_backtest_runner(
    *,
    symbol: str,
    volume: float = 1.0,
    minimum_score: int = 80,
    risk_reward: float = 2.0,
    pending_entry_ttl_candles: int = 4,
) -> BacktestRunner:
    """Build the deterministic Genesis backtest stack for QTR Long.

    This first wiring validates signal/execution mechanics with fixed volume.
    Account-equity position sizing will be layered on top before the five-year
    capital-curve validation.
    """

    analysis_engine = AnalysisEngine(
        swing_engine=SwingEngine(),
        structure_engine=StructureEngine(),
        market_structure_engine=MarketStructureEngine(),
        bos_engine=BOSEngine(),
        choch_engine=CHOCHEngine(),
        trend_engine=TrendEngine(),
        setup_engine=SetupEngine(),
    )
    strategy = QTRLongStrategy(
        analysis_engine=analysis_engine,
        minimum_score=minimum_score,
    )
    decision_engine = LongDecisionEngine()
    risk_manager = LongOnlyRiskManager(
        risk_reward=risk_reward,
        symbol=symbol,
        volume=volume,
    )

    return BacktestRunner(
        symbol=symbol,
        strategy=strategy,
        decision_engine=decision_engine,
        risk_manager=risk_manager,
        pending_entry_ttl_candles=pending_entry_ttl_candles,
    )
