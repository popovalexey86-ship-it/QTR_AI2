from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from core.decision import Decision
from core.pending_entry import PendingEntryStatus
from core.position import Position
from core.setup import Setup
from core.trade_request import TradeRequest
from core.trend import Trend
from infrastructure.bybit.bybit_broker import (
    BybitBroker,
    BybitPendingEntryError,
    BybitTestnetRequiredError,
)
from infrastructure.bybit.bybit_entry_order_snapshot_mapper import (
    BybitEntryOrderSnapshotError,
)


ORDER_LINK_ID = "QTR-0123456789abcdef"
OTHER_ORDER_LINK_ID = "QTR-fedcba9876543210"
EXCHANGE_ORDER_ID = "exchange-order-1"
SIGNAL_TIMESTAMP = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)


def _request(
    *,
    entry: float = 100.0,
    volume: float = 1.0,
) -> TradeRequest:
    return TradeRequest(
        symbol="ETHUSDT",
        decision=Decision.BUY,
        entry=entry,
        stop_loss=95.0,
        take_profit=110.0,
        volume=volume,
        setup=Setup(
            index=1,
            timestamp=SIGNAL_TIMESTAMP,
            trend=Trend.BULLISH,
            entry=entry,
            stop_loss=95.0,
        ),
    )


def _query_response(*items: dict[str, object]) -> dict[str, object]:
    return {"retCode": 0, "result": {"list": list(items)}}


def _order_item(
    status: str,
    *,
    order_link_id: str = ORDER_LINK_ID,
    order_id: str = EXCHANGE_ORDER_ID,
    quantity: str = "1",
    filled: str = "0",
    average_price: str = "",
    rejection_reason: str = "EC_NoError",
) -> dict[str, object]:
    return {
        "orderLinkId": order_link_id,
        "orderId": order_id,
        "orderStatus": status,
        "qty": quantity,
        "cumExecQty": filled,
        "avgPrice": average_price,
        "rejectReason": rejection_reason,
    }


def _broker(*, testnet: bool = True) -> tuple[BybitBroker, Mock]:
    client = Mock()
    client.is_testnet = testnet
    client.get_positions.return_value = {
        "retCode": 0,
        "result": {"list": []},
    }
    client.place_order.return_value = {
        "retCode": 0,
        "result": {
            "orderId": EXCHANGE_ORDER_ID,
            "orderLinkId": ORDER_LINK_ID,
        },
    }
    client.get_open_orders.return_value = _query_response()
    client.get_order_history.return_value = _query_response()
    client.cancel_order.return_value = {
        "retCode": 0,
        "result": {
            "orderId": EXCHANGE_ORDER_ID,
            "orderLinkId": ORDER_LINK_ID,
        },
    }
    return (
        BybitBroker(
            client=client,
            category="linear",
            symbol="BTCUSDT",
        ),
        client,
    )


def _submit(
    broker: BybitBroker,
    *,
    request: TradeRequest | None = None,
    order_link_id: str = ORDER_LINK_ID,
) -> None:
    broker.submit_entry(
        request or _request(),
        order_link_id=order_link_id,
        setup_key="stable-setup-key",
        signal_timestamp=SIGNAL_TIMESTAMP,
    )


def test_testnet_submission_sends_exact_limit_request_and_stores_submitted() -> None:
    broker, client = _broker()

    acknowledgement = broker.submit_entry(
        _request(),
        order_link_id=ORDER_LINK_ID,
        setup_key="stable-setup-key",
        signal_timestamp=SIGNAL_TIMESTAMP,
    )

    assert acknowledgement.order_link_id == ORDER_LINK_ID
    assert acknowledgement.exchange_order_id == EXCHANGE_ORDER_ID
    client.place_order.assert_called_once_with(
        category="linear",
        symbol="BTCUSDT",
        side="Buy",
        orderType="Limit",
        qty="1",
        price="100",
        timeInForce="GTC",
        positionIdx=0,
        orderLinkId=ORDER_LINK_ID,
        reduceOnly=False,
        takeProfit="110",
        stopLoss="95",
        tpslMode="Full",
        tpOrderType="Market",
        slOrderType="Market",
        tpTriggerBy="LastPrice",
        slTriggerBy="LastPrice",
    )
    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.status == PendingEntryStatus.SUBMITTED
    assert pending.exchange_order_id == EXCHANGE_ORDER_ID
    assert pending.request.symbol == "ETHUSDT"
    assert broker.get_open_position() is None


def test_mainnet_submission_is_refused_before_any_order_or_position_call() -> None:
    broker, client = _broker(testnet=False)

    with pytest.raises(BybitTestnetRequiredError, match="Testnet"):
        _submit(broker)

    client.place_order.assert_not_called()
    client.get_positions.assert_not_called()
    assert broker.get_pending_entry() is None


@pytest.mark.parametrize(
    "response",
    [
        {"retCode": 10001, "retMsg": "secret raw payload", "result": {}},
        {"retCode": 0},
        {"retCode": 0, "result": None},
        {"retCode": 0, "result": {}},
        {"retCode": 0, "result": {"orderId": ""}},
    ],
)
def test_invalid_submission_acknowledgement_fails_closed(
    response: dict[str, object],
) -> None:
    broker, client = _broker()
    client.place_order.return_value = response

    with pytest.raises(BybitPendingEntryError) as error:
        _submit(broker)

    assert "secret raw payload" not in str(error.value)
    assert broker.get_pending_entry() is None


def test_mismatched_returned_order_link_id_fails_closed() -> None:
    broker, client = _broker()
    client.place_order.return_value["result"]["orderLinkId"] = OTHER_ORDER_LINK_ID

    with pytest.raises(BybitPendingEntryError, match="conflicting"):
        _submit(broker)

    assert broker.get_pending_entry() is None


def test_identical_active_submission_is_idempotent() -> None:
    broker, client = _broker()
    request = _request()

    first = broker.submit_entry(
        request,
        order_link_id=ORDER_LINK_ID,
        setup_key="stable-setup-key",
        signal_timestamp=SIGNAL_TIMESTAMP,
    )
    second = broker.submit_entry(
        request,
        order_link_id=ORDER_LINK_ID,
        setup_key="stable-setup-key",
        signal_timestamp=SIGNAL_TIMESTAMP,
    )

    assert second == first
    client.place_order.assert_called_once()
    client.get_positions.assert_called_once()


@pytest.mark.parametrize("conflict", ["content", "link"])
def test_active_submission_conflict_fails_closed(conflict: str) -> None:
    broker, client = _broker()
    _submit(broker)

    with pytest.raises(BybitPendingEntryError):
        broker.submit_entry(
            _request(entry=101.0) if conflict == "content" else _request(),
            order_link_id=(
                ORDER_LINK_ID if conflict == "content" else OTHER_ORDER_LINK_ID
            ),
            setup_key="stable-setup-key",
            signal_timestamp=SIGNAL_TIMESTAMP,
        )

    client.place_order.assert_called_once()


def test_open_position_blocks_submission() -> None:
    position_mapper = Mock()
    position_mapper.from_position.return_value = Position(
        ticket="position-1",
        decision=Decision.BUY,
        entry=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        volume=1.0,
        opened_at=SIGNAL_TIMESTAMP,
        symbol="BTCUSDT",
    )
    broker, client = _broker()
    client.get_positions.return_value = {
        "retCode": 0,
        "result": {"list": [{"size": "1"}]},
    }
    broker = BybitBroker(
        client=client,
        category="linear",
        symbol="BTCUSDT",
        position_mapper=position_mapper,
    )

    with pytest.raises(BybitPendingEntryError, match="open position"):
        _submit(broker)

    client.place_order.assert_not_called()
    assert broker.get_pending_entry() is None


def test_realtime_working_snapshot_reconciles_without_history_lookup() -> None:
    broker, client = _broker()
    _submit(broker)
    client.get_open_orders.return_value = _query_response(_order_item("New"))

    snapshot = broker.get_entry_order(ORDER_LINK_ID)

    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.WORKING
    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.status == PendingEntryStatus.WORKING
    client.get_order_history.assert_not_called()


def test_realtime_full_fill_clears_the_active_slot() -> None:
    broker, client = _broker()
    _submit(broker)
    client.get_open_orders.return_value = _query_response(
        _order_item("Filled", filled="1", average_price="100.25")
    )

    snapshot = broker.get_entry_order(ORDER_LINK_ID)

    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.FILLED
    assert snapshot.average_fill_price == 100.25
    assert broker.get_pending_entry() is None


@pytest.mark.parametrize(
    ("exchange_status", "domain_status", "filled", "average_price"),
    [
        ("Filled", PendingEntryStatus.FILLED, "1", "100"),
        ("Cancelled", PendingEntryStatus.CANCELLED, "0", ""),
        ("Rejected", PendingEntryStatus.REJECTED, "0", ""),
    ],
)
def test_realtime_miss_falls_back_to_terminal_history(
    exchange_status: str,
    domain_status: PendingEntryStatus,
    filled: str,
    average_price: str,
) -> None:
    broker, client = _broker()
    _submit(broker)
    client.get_order_history.return_value = _query_response(
        _order_item(
            exchange_status,
            filled=filled,
            average_price=average_price,
            rejection_reason="safe rejection",
        )
    )

    snapshot = broker.get_entry_order(ORDER_LINK_ID)

    assert snapshot is not None
    assert snapshot.status == domain_status
    assert broker.get_pending_entry() is None
    client.get_order_history.assert_called_once()


def test_unknown_order_missing_from_both_queries_returns_none() -> None:
    broker, client = _broker()

    assert broker.get_entry_order(OTHER_ORDER_LINK_ID) is None

    client.get_open_orders.assert_called_once()
    client.get_order_history.assert_called_once()


def test_active_order_missing_from_both_queries_fails_closed() -> None:
    broker, _ = _broker()
    _submit(broker)
    pending = broker.get_pending_entry()

    with pytest.raises(BybitPendingEntryError, match="missing"):
        broker.get_entry_order(ORDER_LINK_ID)

    assert broker.get_pending_entry() == pending


def test_multiple_realtime_matches_fail_closed() -> None:
    broker, client = _broker()
    _submit(broker)
    pending = broker.get_pending_entry()
    client.get_open_orders.return_value = _query_response(
        _order_item("New"),
        _order_item("New"),
    )

    with pytest.raises(BybitEntryOrderSnapshotError, match="multiple"):
        broker.get_entry_order(ORDER_LINK_ID)

    assert broker.get_pending_entry() == pending
    client.get_order_history.assert_not_called()


def test_malformed_realtime_response_preserves_local_state_and_safe_error() -> None:
    broker, client = _broker()
    _submit(broker)
    pending = broker.get_pending_entry()
    client.get_open_orders.return_value = {
        "retCode": 10001,
        "retMsg": "token=https://signed.example/secret",
    }

    with pytest.raises(BybitEntryOrderSnapshotError) as error:
        broker.get_entry_order(ORDER_LINK_ID)

    assert "secret" not in str(error.value)
    assert "signed.example" not in repr(error.value)
    assert broker.get_pending_entry() == pending


def test_transport_error_is_sanitized_and_preserves_local_state() -> None:
    broker, client = _broker()
    _submit(broker)
    pending = broker.get_pending_entry()
    client.get_open_orders.side_effect = RuntimeError(
        "https://api-testnet.bybit.com?api_key=secret&sign=signature"
    )

    with pytest.raises(BybitPendingEntryError) as error:
        broker.get_entry_order(ORDER_LINK_ID)

    assert "secret" not in str(error.value)
    assert "signature" not in repr(error.value)
    assert "bybit.com" not in str(error.value)
    assert broker.get_pending_entry() == pending


def test_non_mapping_response_fails_closed_without_clearing_active_state() -> None:
    broker, client = _broker()
    _submit(broker)
    pending = broker.get_pending_entry()
    client.get_open_orders.return_value = ["raw", "payload"]

    with pytest.raises(BybitPendingEntryError, match="malformed response"):
        broker.get_entry_order(ORDER_LINK_ID)

    assert broker.get_pending_entry() == pending


def test_cancel_acknowledgement_is_asynchronous_and_idempotent() -> None:
    broker, client = _broker()
    _submit(broker)

    broker.cancel_entry(ORDER_LINK_ID)
    broker.cancel_entry(ORDER_LINK_ID)

    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.status == PendingEntryStatus.CANCEL_REQUESTED
    client.cancel_order.assert_called_once_with(
        category="linear",
        symbol="BTCUSDT",
        order_link_id=ORDER_LINK_ID,
        order_id=EXCHANGE_ORDER_ID,
    )


def test_exchange_pending_cancel_reconciles_submitted_to_cancel_requested() -> None:
    broker, client = _broker()
    _submit(broker)
    client.get_open_orders.return_value = _query_response(
        _order_item("PendingCancel")
    )

    snapshot = broker.get_entry_order(ORDER_LINK_ID)

    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.CANCEL_REQUESTED
    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.status == PendingEntryStatus.CANCEL_REQUESTED
    client.cancel_order.assert_not_called()


def test_cancel_error_preserves_original_active_state() -> None:
    broker, client = _broker()
    _submit(broker)
    original = broker.get_pending_entry()
    client.cancel_order.return_value = {
        "retCode": 10001,
        "retMsg": "raw secret response",
    }

    with pytest.raises(BybitPendingEntryError) as error:
        broker.cancel_entry(ORDER_LINK_ID)

    assert "raw secret response" not in str(error.value)
    assert broker.get_pending_entry() == original


def test_cancelled_snapshot_clears_only_after_exchange_confirmation() -> None:
    broker, client = _broker()
    _submit(broker)
    broker.cancel_entry(ORDER_LINK_ID)
    assert broker.get_pending_entry() is not None
    client.get_open_orders.return_value = _query_response(
        _order_item("Cancelled")
    )

    snapshot = broker.get_entry_order(ORDER_LINK_ID)

    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.CANCELLED
    assert broker.get_pending_entry() is None


def test_cancel_requested_does_not_regress_on_stale_new_snapshot() -> None:
    broker, client = _broker()
    _submit(broker)
    broker.cancel_entry(ORDER_LINK_ID)
    client.get_open_orders.return_value = _query_response(_order_item("New"))

    snapshot = broker.get_entry_order(ORDER_LINK_ID)

    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.CANCEL_REQUESTED
    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.status == PendingEntryStatus.CANCEL_REQUESTED


def test_fill_wins_race_after_cancel_acknowledgement() -> None:
    broker, client = _broker()
    _submit(broker)
    broker.cancel_entry(ORDER_LINK_ID)
    client.get_open_orders.return_value = _query_response(
        _order_item("Filled", filled="1", average_price="100.5")
    )

    snapshot = broker.get_entry_order(ORDER_LINK_ID)

    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.FILLED
    assert broker.get_pending_entry() is None


def test_partial_fill_stores_fill_and_requests_one_cancellation() -> None:
    broker, client = _broker()
    _submit(broker)
    client.get_open_orders.return_value = _query_response(
        _order_item("PartiallyFilled", filled="0.4", average_price="99.5")
    )

    first = broker.get_entry_order(ORDER_LINK_ID)
    second = broker.get_entry_order(ORDER_LINK_ID)

    assert first is not None
    assert first.status == PendingEntryStatus.PARTIALLY_FILLED
    assert second is not None
    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.status == PendingEntryStatus.CANCEL_REQUESTED
    assert pending.filled_volume == 0.4
    assert pending.average_fill_price == 99.5
    client.cancel_order.assert_called_once()


@pytest.mark.parametrize(
    ("terminal_status", "filled", "average_price", "expected_status"),
    [
        ("Cancelled", "0.4", "99.5", PendingEntryStatus.CANCELLED),
        ("Filled", "1", "99.75", PendingEntryStatus.FILLED),
    ],
)
def test_partial_fill_terminal_resolution_clears_active_slot(
    terminal_status: str,
    filled: str,
    average_price: str,
    expected_status: PendingEntryStatus,
) -> None:
    broker, client = _broker()
    _submit(broker)
    client.get_open_orders.return_value = _query_response(
        _order_item("PartiallyFilled", filled="0.4", average_price="99.5")
    )
    broker.get_entry_order(ORDER_LINK_ID)
    client.get_open_orders.return_value = _query_response(
        _order_item(
            terminal_status,
            filled=filled,
            average_price=average_price,
        )
    )

    snapshot = broker.get_entry_order(ORDER_LINK_ID)

    assert snapshot is not None
    assert snapshot.status == expected_status
    assert snapshot.filled_volume == float(filled)
    assert broker.get_pending_entry() is None
    client.cancel_order.assert_called_once()


def test_cancel_unknown_is_noop_and_mismatched_active_order_fails_closed() -> None:
    broker, client = _broker()
    broker.cancel_entry(OTHER_ORDER_LINK_ID)
    client.cancel_order.assert_not_called()
    _submit(broker)

    with pytest.raises(BybitPendingEntryError, match="does not match"):
        broker.cancel_entry(OTHER_ORDER_LINK_ID)

    client.cancel_order.assert_not_called()


def test_repeated_identical_working_snapshot_is_idempotent() -> None:
    broker, client = _broker()
    _submit(broker)
    client.get_open_orders.return_value = _query_response(_order_item("New"))

    first = broker.get_entry_order(ORDER_LINK_ID)
    second = broker.get_entry_order(ORDER_LINK_ID)

    assert second == first
    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.status == PendingEntryStatus.WORKING
