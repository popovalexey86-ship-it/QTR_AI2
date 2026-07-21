from datetime import datetime
from unittest.mock import Mock

import pytest
import requests

from core.decision import Decision
from core.notification import NotificationError
from core.position import Position
from core.trade import Trade
from core.trade_statistics import TradeStatistics
from infrastructure.telegram_notifier import TelegramNotifier


TOKEN = "sensitive-test-token"
CHAT_ID = "test-chat"


def make_position() -> Position:
    return Position(
        ticket="position-001", symbol="BTCUSDT", decision=Decision.BUY,
        entry=100.0, stop_loss=95.0, take_profit=110.0, volume=0.01,
        opened_at=datetime(2025, 1, 1, 12, 30),
    )


def make_trade() -> Trade:
    return Trade(
        ticket="trade-001", symbol="BTCUSDT", decision=Decision.SELL,
        entry=100.0, exit=95.0, volume=0.01, pnl=5.0, fees=0.1,
        opened_at=datetime(2025, 1, 1, 12, 30),
        closed_at=datetime(2025, 1, 1, 13, 30),
    )


def make_notifier(response=None, timeout=(3.05, 5.0)):
    if response is None:
        response = Mock()
        response.json.return_value = {"ok": True}
    session = Mock()
    session.post.return_value = response
    notifier = TelegramNotifier(TOKEN, CHAT_ID, timeout=timeout, session=session)
    return notifier, session, response


def test_constructor_does_not_make_http_request():
    session = Mock()
    TelegramNotifier(TOKEN, CHAT_ID, session=session)
    session.post.assert_not_called()


@pytest.mark.parametrize("token, chat_id", [("", CHAT_ID), (TOKEN, ""), (" ", CHAT_ID)])
def test_constructor_rejects_empty_credentials_without_exposing_token(token, chat_id):
    with pytest.raises(ValueError) as error:
        TelegramNotifier(token, chat_id, session=Mock())
    assert TOKEN not in str(error.value)


def test_position_opened_sends_expected_url_payload_and_timeout():
    timeout = (1.0, 2.0)
    notifier, session, response = make_notifier(timeout=timeout)
    notifier.position_opened(make_position())

    response.raise_for_status.assert_called_once_with()
    url = session.post.call_args.args[0]
    kwargs = session.post.call_args.kwargs
    assert url == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert kwargs["timeout"] == timeout
    assert kwargs["json"]["chat_id"] == CHAT_ID
    assert kwargs["json"]["text"] == (
        "\U0001f7e2 Position Opened\nSymbol: BTCUSDT\nDirection: BUY\n"
        "Entry: 100.0\nVolume: 0.01\nTicket: position-001\n"
        "Opened at: 2025-01-01T12:30:00"
    )


def test_trade_closed_includes_trade_and_current_statistics():
    notifier, session, _ = make_notifier()
    trade = make_trade()
    statistics = TradeStatistics()
    statistics.add_trade(trade)
    notifier.trade_closed(trade, statistics)

    message = session.post.call_args.kwargs["json"]["text"]
    assert message == (
        "\U0001f534 Trade Closed\nSymbol: BTCUSDT\nDirection: SELL\n"
        "Entry: 100.0\nExit: 95.0\nVolume: 0.01\nPnL: 5.0\nFees: 0.1\n"
        "Ticket: trade-001\nClosed at: 2025-01-01T13:30:00\n\n"
        "Total trades: 1\nWin rate: 100.00%\nNet PnL: 5.0"
    )


@pytest.mark.parametrize(
    "method_name, arguments, expected_message",
    [
        ("runtime_started", (), "🚀 QTR_AI2 Bot Started"),
        ("runtime_stopped", (), "🛑 QTR_AI2 Bot Stopped"),
        (
            "runtime_failed",
            ("Trading loop error: RuntimeError",),
            "⚠️ QTR_AI2 Critical Runtime Error\n"
            "Error: Trading loop error: RuntimeError",
        ),
    ],
)
def test_lifecycle_notifications_have_expected_format(
    method_name,
    arguments,
    expected_message,
):
    notifier, session, _ = make_notifier()

    getattr(notifier, method_name)(*arguments)

    assert session.post.call_args.kwargs["json"]["text"] == expected_message


@pytest.mark.parametrize(
    "request_error",
    [requests.Timeout(f"timeout {TOKEN}"), requests.ConnectionError(f"connection {TOKEN}"),
     requests.RequestException(f"request {TOKEN}")],
)
def test_request_errors_are_wrapped_without_exposing_token(request_error):
    notifier, session, _ = make_notifier()
    session.post.side_effect = request_error
    with pytest.raises(NotificationError) as error:
        notifier.position_opened(make_position())
    assert TOKEN not in str(error.value)


def test_http_error_is_wrapped_without_exposing_token():
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError(f"bad URL {TOKEN}")
    notifier, _, _ = make_notifier(response=response)
    with pytest.raises(NotificationError) as error:
        notifier.position_opened(make_position())
    assert TOKEN not in str(error.value)


@pytest.mark.parametrize("payload", [{"ok": False}, {}, [], "unexpected"])
def test_unsuccessful_or_invalid_telegram_payload_raises(payload):
    response = Mock()
    response.json.return_value = payload
    notifier, _, _ = make_notifier(response=response)
    with pytest.raises(NotificationError):
        notifier.position_opened(make_position())


def test_malformed_json_raises_notification_error():
    response = Mock()
    response.json.side_effect = ValueError("not json")
    notifier, _, _ = make_notifier(response=response)
    with pytest.raises(NotificationError):
        notifier.position_opened(make_position())
