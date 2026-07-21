from types import SimpleNamespace
from unittest.mock import Mock, call

import main
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
