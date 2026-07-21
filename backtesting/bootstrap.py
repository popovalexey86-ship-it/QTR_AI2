from backtesting.backtest_runner import BacktestRunner
from core.analysis_engine import AnalysisEngine
from core.bos_engine import BOSEngine
from core.choch_engine import CHOCHEngine
from core.decision_engine import DecisionEngine
from core.risk_manager import RiskManager
from core.setup_engine import SetupEngine
from core.swing_engine import SwingEngine
from core.trend_engine import TrendEngine
from market_structure.market_structure_engine import MarketStructureEngine
from market_structure.structure_engine import StructureEngine
from strategies.smc_strategy import SMCStrategy


def create_sample_backtest_runner() -> BacktestRunner:
    analysis_engine = AnalysisEngine(
        swing_engine=SwingEngine(),
        structure_engine=StructureEngine(),
        market_structure_engine=MarketStructureEngine(),
        bos_engine=BOSEngine(),
        choch_engine=CHOCHEngine(),
        trend_engine=TrendEngine(),
        setup_engine=SetupEngine(),
    )
    return BacktestRunner(
        symbol="BTCUSDT",
        strategy=SMCStrategy(analysis_engine),
        decision_engine=DecisionEngine(),
        risk_manager=RiskManager(risk_reward=2.0),
    )
