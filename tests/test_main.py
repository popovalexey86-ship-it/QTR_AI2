import argparse
from types import SimpleNamespace
from unittest.mock import Mock, call
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import main
from backtesting.historical_data import HistoricalDataResult
from core.candle import Candle
from core.notification import NotificationError


def make_runtime():
    collector = Mock()
    container = SimpleNamespace(collector=collector, config=Mock())
    return container, Mock(), Mock()


def test_live_cycle_logs_startup_and_stops_cleanly_on_keyboard_interrupt(
    monkeypatch,
):
    container, engine, notifier = make_runtime()
    container.collector.collect.side_effect = KeyboardInterrupt
    logger = Mock()
    monkeypatch.setattr(main, "logger", logger)

    main.run_trading_cycle(container, engine, notifier)

    assert logger.info.call_args_list == [
        call("Trading cycle started."),
        call("Trading cycle stopped."),
    ]
    logger.exception.assert_not_called()
    notifier.runtime_started.assert_called_once_with()
    notifier.runtime_stopped.assert_called_once_with()


def test_runtime_error_notifies_with_sanitized_message_and_retries(monkeypatch):
    container, engine, notifier = make_runtime()
    container.collector.collect.side_effect = [
        RuntimeError("secret-token=https://private.example"),
        KeyboardInterrupt,
    ]
    logger = Mock()
    sleep = Mock()
    monkeypatch.setattr(main, "logger", logger)
    monkeypatch.setattr(main.time, "sleep", sleep)

    main.run_trading_cycle(container, engine, notifier)

    notifier.runtime_failed.assert_called_once_with(
        "Trading loop error: RuntimeError"
    )
    sleep.assert_called_once_with(10)
    logged_text = " ".join(str(item) for item in logger.mock_calls)
    assert "secret-token" not in logged_text
    assert "private.example" not in logged_text


def test_notification_failures_do_not_terminate_live_cycle(monkeypatch):
    container, engine, notifier = make_runtime()
    container.collector.collect.side_effect = [ValueError("bad data"), KeyboardInterrupt]
    notifier.runtime_started.side_effect = NotificationError("failed")
    notifier.runtime_failed.side_effect = NotificationError("failed")
    notifier.runtime_stopped.side_effect = NotificationError("failed")
    logger = Mock()
    monkeypatch.setattr(main, "logger", logger)
    monkeypatch.setattr(main.time, "sleep", Mock())

    main.run_trading_cycle(container, engine, notifier)

    notifier.runtime_started.assert_called_once_with()
    notifier.runtime_failed.assert_called_once_with(
        "Trading loop error: ValueError"
    )
    notifier.runtime_stopped.assert_called_once_with()
    assert logger.error.call_count == 4


def test_main_test_telegram_path_remains_separate_from_live_cycle(monkeypatch):
    container = Mock()
    engine = Mock()
    send_test = Mock()
    run_cycle = Mock()
    monkeypatch.setattr(main, "build_trading_engine", lambda: (container, engine))
    monkeypatch.setattr(main, "send_telegram_test", send_test)
    monkeypatch.setattr(main, "run_trading_cycle", run_cycle)

    main.main(run_loop=True, test_telegram=True)

    send_test.assert_called_once_with(container)
    run_cycle.assert_not_called()


def test_send_telegram_test_uses_public_connection_method(monkeypatch):
    notifier = Mock()
    notifier_factory = Mock(return_value=notifier)
    container = SimpleNamespace(
        config=SimpleNamespace(
            telegram_bot_token="test-token",
            telegram_chat_id="test-chat",
        )
    )
    logger = Mock()
    monkeypatch.setattr(main, "TelegramNotifier", notifier_factory)
    monkeypatch.setattr(main, "logger", logger)

    main.send_telegram_test(container)

    notifier_factory.assert_called_once_with(
        bot_token="test-token",
        chat_id="test-chat",
    )
    notifier.test_connection.assert_called_once_with()
    logger.info.assert_called_once_with("Telegram test notification sent.")


def test_backtest_sample_does_not_build_live_dependencies(monkeypatch):
    run_backtest = Mock()
    build_live = Mock(side_effect=AssertionError("live dependencies were built"))
    monkeypatch.setattr(main, "run_sample_backtest", run_backtest)
    monkeypatch.setattr(main, "build_trading_engine", build_live)

    main.main(backtest_sample=True)

    run_backtest.assert_called_once_with()
    build_live.assert_not_called()


def test_sample_backtest_prints_summary_without_network(monkeypatch, capsys):
    def fail_live_build():
        raise AssertionError("live dependencies were built")

    monkeypatch.setattr(main, "build_trading_engine", fail_live_build)

    main.run_sample_backtest()

    output = capsys.readouterr().out
    assert "Backtest summary: BTCUSDT" in output
    assert "Candles processed: 10" in output
    assert "Final position:" in output


def test_parse_utc_datetime_accepts_z_and_rejects_naive_or_non_utc():
    assert main.parse_utc_datetime("2025-01-01T00:00:00Z") == datetime(
        2025, 1, 1, tzinfo=UTC
    )

    with pytest.raises(argparse.ArgumentTypeError, match="timezone-aware UTC"):
        main.parse_utc_datetime("2025-01-01T00:00:00")
    with pytest.raises(argparse.ArgumentTypeError, match="must use UTC"):
        main.parse_utc_datetime("2025-01-01T01:00:00+01:00")


def test_historical_backtest_path_does_not_build_live_dependencies(monkeypatch):
    run_historical = Mock()
    build_live = Mock(side_effect=AssertionError("live dependencies were built"))
    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = start + timedelta(minutes=2)
    monkeypatch.setattr(main, "run_bybit_backtest", run_historical)
    monkeypatch.setattr(main, "build_trading_engine", build_live)

    main.main(
        backtest_bybit=True,
        symbol="BTCUSDT",
        interval="1",
        start=start,
        end=end,
        refresh_cache=True,
        history_window=20,
    )

    run_historical.assert_called_once_with(
        symbol="BTCUSDT",
        interval="1",
        start=start,
        end=end,
        refresh_cache=True,
        history_window=20,
        verbose=False,
    )
    build_live.assert_not_called()


def test_historical_backtest_uses_no_live_or_telegram_network(monkeypatch, capsys):
    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = start + timedelta(minutes=1)
    candle = Candle(
        timestamp=start,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1.0,
    )

    def fake_load_historical_data(**kwargs):
        return HistoricalDataResult(
            candles=(candle,),
            source="cache",
            cache_path=Path("fake-cache.json"),
        )

    def fail(*args, **kwargs):
        raise AssertionError("live or Telegram dependency was used")

    monkeypatch.setattr(
        "backtesting.historical_data.load_historical_data",
        fake_load_historical_data,
    )
    monkeypatch.setattr(main, "build_trading_engine", fail)
    monkeypatch.setattr(
        "infrastructure.telegram_notifier.TelegramNotifier._send",
        fail,
    )

    main.run_bybit_backtest(
        symbol="BTCUSDT",
        interval="1",
        start=start,
        end=end,
    )

    captured = capsys.readouterr()
    output = captured.out
    assert "Source: cache" in output
    assert "Candles downloaded: 1" in output
    assert "Candles processed: 1" in output
    assert "Trading cycle started" not in captured.err
    assert "Setup not found" not in captured.err
