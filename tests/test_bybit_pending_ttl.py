from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

from core.pending_entry import PendingEntry, PendingEntryStatus
from infrastructure.bybit.bybit_broker import (
    BybitBroker,
    BybitPendingEntryError,
    BybitPendingEntryPersistenceError,
)
from infrastructure.bybit.bybit_pending_entry_store import (
    SCHEMA_VERSION,
    BybitPendingEntryStore,
    BybitPendingEntryStoreError,
    PersistedBybitPendingEntry,
)
from tests.test_bybit_pending_broker import (
    EXCHANGE_ORDER_ID,
    ORDER_LINK_ID,
    SIGNAL_TIMESTAMP,
    _broker,
    _order_item,
    _query_response,
    _request,
    _submit,
)


CANDLES = tuple(
    SIGNAL_TIMESTAMP + timedelta(minutes=15 * index)
    for index in range(1, 7)
)


class FailingExpiryStore(BybitPendingEntryStore):
    def save(self, state: PersistedBybitPendingEntry) -> None:
        if state.pending_entry.expiry_requested:
            raise BybitPendingEntryStoreError("sensitive filesystem failure")
        super().save(state)


def _live_broker(
    tmp_path: Path,
    *,
    store: BybitPendingEntryStore | None = None,
) -> tuple[BybitBroker, Mock, BybitPendingEntryStore]:
    selected_store = store or BybitPendingEntryStore(tmp_path / "pending.json")
    broker, client = _broker(pending_entry_store=selected_store)
    _submit(broker)
    client.get_open_orders.return_value = _query_response(_order_item("New"))
    return broker, client, selected_store


def test_ttl_c1_through_c4_and_nth_candle_remains_fillable(tmp_path: Path) -> None:
    broker, client, store = _live_broker(tmp_path)

    for index in range(1, 4):
        pending = broker.age_pending_entry(CANDLES[:index], ttl_candles=4)
        assert pending is not None
        assert pending.completed_candles_active == index
        assert pending.expiry_requested is False
        client.cancel_order.assert_not_called()

    pending = broker.age_pending_entry(CANDLES[:4], ttl_candles=4)

    assert pending is not None
    assert pending.completed_candles_active == 4
    assert pending.expiry_requested is True
    assert pending.status == PendingEntryStatus.CANCEL_REQUESTED
    client.cancel_order.assert_called_once()
    assert client.method_calls[-2][0] == "get_open_orders"
    assert client.method_calls[-1][0] == "cancel_order"
    loaded = store.load()
    assert loaded is not None
    assert loaded.pending_entry.expiry_requested is True
    assert loaded.pending_entry.status == PendingEntryStatus.CANCEL_REQUESTED
    assert loaded.last_aged_candle_timestamp == CANDLES[3]


def test_fill_observed_on_c4_wins_before_expiry(tmp_path: Path) -> None:
    broker, client, store = _live_broker(tmp_path)
    broker.age_pending_entry(CANDLES[:3], ttl_candles=4)
    client.get_open_orders.return_value = _query_response(
        _order_item("Filled", filled="1", average_price="100")
    )

    result = broker.age_pending_entry(CANDLES[:4], ttl_candles=4)

    assert result is None
    client.cancel_order.assert_not_called()
    assert store.load() is None


def test_duplicate_candles_are_idempotent(tmp_path: Path) -> None:
    broker, _, store = _live_broker(tmp_path)

    first = broker.age_pending_entry((CANDLES[0], CANDLES[0]), ttl_candles=4)
    second = broker.age_pending_entry((CANDLES[0],), ttl_candles=4)

    assert first is not None
    assert second is not None
    assert first.completed_candles_active == 1
    assert second.completed_candles_active == 1
    loaded = store.load()
    assert loaded is not None
    assert loaded.last_aged_candle_timestamp == CANDLES[0]


def test_multiple_missed_candles_catch_up_and_pre_signal_is_ignored(
    tmp_path: Path,
) -> None:
    broker, client, _ = _live_broker(tmp_path)
    pre_signal = SIGNAL_TIMESTAMP - timedelta(minutes=15)

    pending = broker.age_pending_entry(
        (CANDLES[2], pre_signal, CANDLES[0], CANDLES[1], CANDLES[1]),
        ttl_candles=4,
    )

    assert pending is not None
    assert pending.completed_candles_active == 3
    client.cancel_order.assert_not_called()


def test_timestamp_regression_fails_closed(tmp_path: Path) -> None:
    broker, _, store = _live_broker(tmp_path)
    broker.age_pending_entry(CANDLES[:2], ttl_candles=4)

    with pytest.raises(BybitPendingEntryError, match="regressed"):
        broker.age_pending_entry((CANDLES[0],), ttl_candles=4)

    loaded = store.load()
    assert loaded is not None
    assert loaded.pending_entry.completed_candles_active == 2


@pytest.mark.parametrize("ttl", [0, -1, True, 1.5])
def test_invalid_ttl_is_rejected(tmp_path: Path, ttl: int) -> None:
    broker, client, _ = _live_broker(tmp_path)

    with pytest.raises(BybitPendingEntryError, match="positive integer"):
        broker.age_pending_entry(CANDLES, ttl_candles=ttl)

    client.get_open_orders.assert_not_called()


def test_expiry_persistence_failure_prevents_cancel_and_rolls_back_age(
    tmp_path: Path,
) -> None:
    store = FailingExpiryStore(tmp_path / "pending.json")
    broker, client, _ = _live_broker(tmp_path, store=store)
    broker.age_pending_entry(CANDLES[:3], ttl_candles=4)

    with pytest.raises(BybitPendingEntryPersistenceError) as error:
        broker.age_pending_entry(CANDLES[:4], ttl_candles=4)

    assert "sensitive" not in str(error.value)
    client.cancel_order.assert_not_called()
    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.completed_candles_active == 3
    assert pending.expiry_requested is False


def test_expiry_marker_is_durable_before_cancel_request(tmp_path: Path) -> None:
    broker, client, store = _live_broker(tmp_path)

    def inspect_persisted_marker(**kwargs: object) -> dict[str, object]:
        loaded = store.load()
        assert loaded is not None
        assert loaded.pending_entry.expiry_requested is True
        assert loaded.pending_entry.status == PendingEntryStatus.WORKING
        return {
            "retCode": 0,
            "result": {
                "orderId": EXCHANGE_ORDER_ID,
                "orderLinkId": ORDER_LINK_ID,
            },
        }

    client.cancel_order.side_effect = inspect_persisted_marker

    broker.age_pending_entry(CANDLES[:4], ttl_candles=4)

    client.cancel_order.assert_called_once()


def test_repeated_aging_sends_only_one_cancel(tmp_path: Path) -> None:
    broker, client, _ = _live_broker(tmp_path)
    broker.age_pending_entry(CANDLES[:4], ttl_candles=4)

    broker.age_pending_entry(CANDLES[:5], ttl_candles=4)

    client.cancel_order.assert_called_once()


def test_recovery_resumes_crash_between_expiry_persist_and_cancel(
    tmp_path: Path,
) -> None:
    store = BybitPendingEntryStore(tmp_path / "pending.json")
    request = replace(_request(), symbol="BTCUSDT")
    expiring = PendingEntry(
        order_link_id=ORDER_LINK_ID,
        exchange_order_id=EXCHANGE_ORDER_ID,
        setup_key="stable-setup-key",
        request=request,
        signal_timestamp=SIGNAL_TIMESTAMP,
        status=PendingEntryStatus.WORKING,
        completed_candles_active=4,
        expiry_requested=True,
    )
    store.save(
        PersistedBybitPendingEntry(
            schema_version=SCHEMA_VERSION,
            pending_entry=expiring,
            last_aged_candle_timestamp=CANDLES[3],
        )
    )
    broker, client = _broker(pending_entry_store=store)
    client.list_open_orders.return_value = _query_response(_order_item("New"))

    first = broker.recover_pending_entry()
    second = broker.recover_pending_entry()

    assert first is not None
    assert first.status == PendingEntryStatus.CANCEL_REQUESTED
    assert second == first
    client.cancel_order.assert_called_once()


def test_cancelled_zero_fill_after_ttl_becomes_expired(tmp_path: Path) -> None:
    broker, client, store = _live_broker(tmp_path)
    broker.age_pending_entry(CANDLES[:4], ttl_candles=4)
    client.get_open_orders.return_value = _query_response(
        _order_item("Cancelled")
    )

    snapshot = broker.get_entry_order(ORDER_LINK_ID)

    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.EXPIRED
    assert broker.get_pending_entry() is None
    assert store.load() is None


def test_ordinary_cancelled_remains_cancelled(tmp_path: Path) -> None:
    broker, client, store = _live_broker(tmp_path)
    broker.cancel_entry(ORDER_LINK_ID)
    client.get_open_orders.return_value = _query_response(
        _order_item("Cancelled")
    )

    snapshot = broker.get_entry_order(ORDER_LINK_ID)

    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.CANCELLED
    assert store.load() is None


def test_partial_fill_cancellation_is_not_expired(tmp_path: Path) -> None:
    store = BybitPendingEntryStore(tmp_path / "pending.json")
    request = replace(_request(), symbol="BTCUSDT")
    partial = PendingEntry(
        order_link_id=ORDER_LINK_ID,
        exchange_order_id=EXCHANGE_ORDER_ID,
        setup_key="stable-setup-key",
        request=request,
        signal_timestamp=SIGNAL_TIMESTAMP,
        status=PendingEntryStatus.CANCEL_REQUESTED,
        completed_candles_active=4,
        filled_volume=0.4,
        average_fill_price=99.5,
        expiry_requested=True,
    )
    store.save(
        PersistedBybitPendingEntry(
            schema_version=SCHEMA_VERSION,
            pending_entry=partial,
            last_aged_candle_timestamp=CANDLES[3],
        )
    )
    broker, client = _broker(pending_entry_store=store)
    client.get_order_history.return_value = _query_response(
        _order_item("Cancelled", filled="0.4", average_price="99.5")
    )

    assert broker.recover_pending_entry() is None
    assert broker._entry_orders[ORDER_LINK_ID].status == PendingEntryStatus.CANCELLED


def test_fill_wins_after_expiry_cancel_acknowledgement(tmp_path: Path) -> None:
    broker, client, store = _live_broker(tmp_path)
    broker.age_pending_entry(CANDLES[:4], ttl_candles=4)
    client.get_open_orders.return_value = _query_response(
        _order_item("Filled", filled="1", average_price="100")
    )

    snapshot = broker.get_entry_order(ORDER_LINK_ID)

    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.FILLED
    assert broker.get_pending_entry() is None
    assert store.load() is None
