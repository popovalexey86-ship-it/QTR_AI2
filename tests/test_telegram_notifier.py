from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
import requests

from core.decision import Decision
from core.notification import NotificationError
from core.position import Position
from core.trade import Trade
from core.trade_statistics import TradeStatistics
from core.pending_entry import PendingEntryStatus
from core.pending_entry_event import PendingEntryEvent, PendingEntryEventKind
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


def make_pending_event(
    status: PendingEntryStatus,
    *,
    kind: PendingEntryEventKind = PendingEntryEventKind.STATUS_CHANGED,
    filled_volume: float = 0.0,
    average_fill_price: float | None = None,
    exchange_order_id: str | None = "exchange-1",
    rejection_reason: str | None = None,
) -> PendingEntryEvent:
    return PendingEntryEvent(
        kind=kind,
        order_link_id="QTR-safe-order",
        exchange_order_id=exchange_order_id,
        symbol="BTCUSDT",
        decision=Decision.BUY,
        status=status,
        previous_status=PendingEntryStatus.SUBMITTED,
        entry=100.0,
        requested_volume=1.0,
        filled_volume=filled_volume,
        average_fill_price=average_fill_price,
        rejection_reason=rejection_reason,
        signal_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )


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


@pytest.mark.parametrize(
    ("event", "expected_title"),
    [
        (
            make_pending_event(
                PendingEntryStatus.SUBMITTED,
                kind=PendingEntryEventKind.SUBMITTED,
            ),
            "Pending Entry Submitted",
        ),
        (
            make_pending_event(
                PendingEntryStatus.WORKING,
                kind=PendingEntryEventKind.RECOVERED,
            ),
            "Pending Entry Recovered",
        ),
        (make_pending_event(PendingEntryStatus.WORKING), "Pending Entry Working"),
        (
            make_pending_event(
                PendingEntryStatus.PARTIALLY_FILLED,
                filled_volume=0.4,
                average_fill_price=99.5,
            ),
            "Pending Entry Partially Filled",
        ),
        (
            make_pending_event(PendingEntryStatus.CANCEL_REQUESTED),
            "Pending Entry Cancellation Requested",
        ),
        (
            make_pending_event(
                PendingEntryStatus.FILLED,
                kind=PendingEntryEventKind.TERMINAL,
                filled_volume=1.0,
                average_fill_price=100.0,
            ),
            "Pending Entry Filled",
        ),
        (
            make_pending_event(
                PendingEntryStatus.CANCELLED,
                kind=PendingEntryEventKind.TERMINAL,
            ),
            "Pending Entry Cancelled",
        ),
        (
            make_pending_event(
                PendingEntryStatus.EXPIRED,
                kind=PendingEntryEventKind.TERMINAL,
            ),
            "Pending Entry Expired",
        ),
        (
            make_pending_event(
                PendingEntryStatus.REJECTED,
                kind=PendingEntryEventKind.TERMINAL,
                rejection_reason="safe reason",
            ),
            "Pending Entry Rejected",
        ),
    ],
)
def test_pending_entry_lifecycle_message_formats(
    event: PendingEntryEvent,
    expected_title: str,
) -> None:
    notifier, session, _ = make_notifier()

    notifier.pending_entry_event(event)

    message = session.post.call_args.kwargs["json"]["text"]
    assert message.startswith(expected_title)
    assert "Symbol: BTCUSDT" in message
    assert "Direction: BUY" in message
    assert "OrderLinkId: QTR-safe-order" in message
    assert TOKEN not in message
    assert "http" not in message.lower()
    if event.filled_volume > 0:
        assert f"Filled volume: {event.filled_volume}" in message
    else:
        assert "Filled volume:" not in message
    if event.rejection_reason is not None:
        assert "Reason: safe reason" in message


def test_pending_message_omits_absent_optional_fields() -> None:
    notifier, session, _ = make_notifier()
    event = make_pending_event(
        PendingEntryStatus.WORKING,
        exchange_order_id=None,
    )

    notifier.pending_entry_event(event)

    message = session.post.call_args.kwargs["json"]["text"]
    assert "Exchange order ID:" not in message
    assert "Average fill price:" not in message
    assert "Reason:" not in message
