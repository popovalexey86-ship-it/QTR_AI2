from datetime import datetime
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
from core.trade import Trade
from infrastructure.csv_trade_journal import CsvTradeJournal
from infrastructure.null_notifier import NullNotifier
from infrastructure.telegram_notifier import TelegramNotifier
from engine.trading_engine import TradingEngine


def test_bootstrap_creates_trading_engine_with_position_monitor(tmp_path):
    container = SimpleNamespace(
        broker=Mock(),
        config=SimpleNamespace(
            trade_journal_path=tmp_path / "trades.csv",
            telegram_enabled=False,
            telegram_bot_token=None,
            telegram_chat_id=None,
            trade_symbol="BTCUSDT",
            trade_volume=0.01,
        ),
    )

    engine = create_trading_engine(container)

    assert isinstance(engine, TradingEngine)
    assert isinstance(engine._position_monitor, PositionMonitor)
    assert isinstance(engine._position_monitor._statistics, TradeStatistics)
    assert isinstance(engine._position_monitor._journal, CsvTradeJournal)
    assert isinstance(engine._position_monitor._notifier, NullNotifier)


def test_trading_cycle_updates_position_monitor_before_analysis():
    strategy = Mock()
    strategy.analyze.return_value = AnalysisContext(market_data=Mock())
    position_monitor = Mock()
    position_monitor.has_open_position.return_value = False
    execution = Mock()
    execution.has_pending_entry.return_value = False

    engine = TradingEngine(
        strategy=strategy,
        decision_engine=Mock(),
        risk_manager=Mock(),
        execution=execution,
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

    monitor = PositionMonitor(
        execution, TradeStatistics(), TradeJournal(), NullNotifier()
    )

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


def test_bootstrap_hydrates_statistics_from_csv_journal(tmp_path):
    path = tmp_path / "trades.csv"
    trade = Trade(
        ticket="trade-1",
        symbol="BTCUSDT",
        decision=Decision.BUY,
        entry=100.0,
        exit=105.0,
        volume=0.01,
        pnl=5.0,
        fees=0.1,
        opened_at=datetime(2025, 1, 1),
        closed_at=datetime(2025, 1, 2),
    )
    CsvTradeJournal(path).add_trade(trade)
    container = SimpleNamespace(
        broker=Mock(),
        config=SimpleNamespace(
            trade_journal_path=path,
            telegram_enabled=False,
            telegram_bot_token=None,
            telegram_chat_id=None,
            trade_symbol="BTCUSDT",
            trade_volume=0.01,
        ),
    )

    engine = create_trading_engine(container)

    assert engine._position_monitor._statistics.trades == (trade,)


def test_bootstrap_selects_telegram_notifier_without_sending_network_request(tmp_path):
    container = SimpleNamespace(
        broker=Mock(),
        config=SimpleNamespace(
            trade_journal_path=tmp_path / "trades.csv",
            telegram_enabled=True,
            telegram_bot_token="test-token",
            telegram_chat_id="test-chat",
            trade_symbol="BTCUSDT",
            trade_volume=0.01,
        ),
    )

    engine = create_trading_engine(container)

    assert isinstance(engine._position_monitor._notifier, TelegramNotifier)
