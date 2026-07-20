from types import SimpleNamespace
from unittest.mock import Mock

import app
import main
from config.bootstrap import create_trading_engine
from core.analysis_context import AnalysisContext
from core.decision import Decision
from core.position_monitor import PositionMonitor
from core.position import Position
from core.trade_statistics import TradeStatistics
from core.trade_journal import TradeJournal
from engine.trading_engine import TradingEngine


def test_bootstrap_creates_trading_engine_with_position_monitor():
    container = SimpleNamespace(broker=Mock())

    engine = create_trading_engine(container)

    assert isinstance(engine, TradingEngine)
    assert isinstance(engine._position_monitor, PositionMonitor)
    assert isinstance(engine._position_monitor._statistics, TradeStatistics)
    assert isinstance(engine._position_monitor._journal, TradeJournal)


def test_trading_cycle_updates_position_monitor_before_analysis():
    strategy = Mock()
    strategy.analyze.return_value = AnalysisContext(market_data=Mock())
    position_monitor = Mock()

    engine = TradingEngine(
        strategy=strategy,
        decision_engine=Mock(),
        risk_manager=Mock(),
        execution=Mock(),
        position_monitor=position_monitor,
    )

    engine.process(Mock())

    position_monitor.update.assert_called_once_with()
    strategy.analyze.assert_called_once()


def test_position_monitor_update_accepts_domain_position():
    position = Position(
        ticket="ticket-1",
        decision=Decision.BUY,
        entry=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        volume=0.01,
        opened_at=Mock(),
    )
    execution = Mock()
    execution.get_open_position.return_value = position

    monitor = PositionMonitor(execution, TradeStatistics(), TradeJournal())

    monitor.update()

    assert monitor.position is position


def test_main_assembles_without_starting_live_cycle(monkeypatch):
    container = Mock()
    engine = Mock()
    monkeypatch.setattr(main, "build_trading_engine", lambda: (container, engine))
    run_cycle = Mock()
    monkeypatch.setattr(main, "run_trading_cycle", run_cycle)

    main.main()

    run_cycle.assert_not_called()


def test_app_uses_safe_application_entrypoint(monkeypatch):
    run_application = Mock()
    monkeypatch.setattr(app, "run_application", run_application)

    app.main()

    run_application.assert_called_once_with(run_loop=False)
