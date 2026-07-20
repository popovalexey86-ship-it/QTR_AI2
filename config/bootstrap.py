from infrastructure.container import Container

from core.analysis_engine import AnalysisEngine

from core.swing_engine import SwingEngine
from market_structure.structure_engine import StructureEngine
from market_structure.market_structure_engine import MarketStructureEngine

from core.bos_engine import BOSEngine
from core.choch_engine import CHOCHEngine
from core.trend_engine import TrendEngine
from core.setup_engine import SetupEngine
from core.decision_engine import DecisionEngine

from core.execution import Execution
from core.position_monitor import PositionMonitor
from core.risk_manager import RiskManager
from core.trade_statistics import TradeStatistics

from engine.trading_engine import TradingEngine
from strategies.smc_strategy import SMCStrategy


def create_trading_engine(
    container: Container,
) -> TradingEngine:
    """
    Собирает все зависимости торгового движка.
    """

    # Analysis engines
    swing_engine = SwingEngine()
    structure_engine = StructureEngine()
    market_structure_engine = MarketStructureEngine()

    bos_engine = BOSEngine()
    choch_engine = CHOCHEngine()
    trend_engine = TrendEngine()
    setup_engine = SetupEngine()
    decision_engine = DecisionEngine()

    # Analysis
    analysis_engine = AnalysisEngine(
        swing_engine=swing_engine,
        structure_engine=structure_engine,
        market_structure_engine=market_structure_engine,
        bos_engine=bos_engine,
        choch_engine=choch_engine,
        trend_engine=trend_engine,
        setup_engine=setup_engine,
    )

    # Strategy
    strategy = SMCStrategy(
        analysis_engine=analysis_engine,
    )

    # Risk & Execution
    risk_manager = RiskManager(
        risk_reward=2.0,
    )

    execution = Execution(
        broker=container.broker,
    )
    statistics = TradeStatistics()
    position_monitor = PositionMonitor(
        execution=execution,
        statistics=statistics,
    )

    # Trading Engine
    return TradingEngine(
        strategy=strategy,
        decision_engine=decision_engine,
        risk_manager=risk_manager,
        execution=execution,
        position_monitor=position_monitor,
    )
