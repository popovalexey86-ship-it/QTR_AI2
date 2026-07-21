from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from core.pending_entry import PendingEntry, PendingEntryStatus
from infrastructure.bybit.bybit_broker import (
    BybitActiveOrderConflictError,
    BybitBroker,
    BybitPendingEntryPersistenceError,
    BybitPendingEntryRecoveryError,
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
    OTHER_ORDER_LINK_ID,
    SIGNAL_TIMESTAMP,
    _broker,
    _order_item,
    _query_response,
    _request,
    _submit,
)


LAST_AGED = datetime(2026, 1, 2, 3, 9, tzinfo=UTC)


class RecordingStore(BybitPendingEntryStore):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.saved_statuses: list[PendingEntryStatus] = []

    def save(self, state: PersistedBybitPendingEntry) -> None:
        self.saved_statuses.append(state.pending_entry.status)
        super().save(state)


class FailingSaveStore(BybitPendingEntryStore):
    def save(self, state: PersistedBybitPendingEntry) -> None:
        raise BybitPendingEntryStoreError("sensitive filesystem details")


class FailingClearStore(BybitPendingEntryStore):
    def clear(self) -> None:
        raise BybitPendingEntryStoreError("sensitive filesystem details")


def _persisted_state(
    *,
    order_link_id: str = ORDER_LINK_ID,
    status: PendingEntryStatus = PendingEntryStatus.SUBMITTED,
    completed_candles_active: int = 2,
) -> PersistedBybitPendingEntry:
    request = replace(_request(), symbol="BTCUSDT")
    return PersistedBybitPendingEntry(
        schema_version=SCHEMA_VERSION,
        pending_entry=PendingEntry(
            order_link_id=order_link_id,
            exchange_order_id=EXCHANGE_ORDER_ID,
            setup_key="stable-setup-key",
            request=request,
            signal_timestamp=SIGNAL_TIMESTAMP,
            status=status,
            completed_candles_active=completed_candles_active,
        ),
        last_aged_candle_timestamp=LAST_AGED,
    )


def _saved_store(tmp_path: Path) -> BybitPendingEntryStore:
    store = BybitPendingEntryStore(tmp_path / "pending.json")
    store.save(_persisted_state())
    return store


def test_submit_persists_submitted_state(tmp_path: Path) -> None:
    store = BybitPendingEntryStore(tmp_path / "pending.json")
    broker, _ = _broker(pending_entry_store=store)

    _submit(broker)

    loaded = store.load()
    assert loaded is not None
    assert loaded.pending_entry.status == PendingEntryStatus.SUBMITTED
    assert loaded.pending_entry.exchange_order_id == EXCHANGE_ORDER_ID


def test_working_reconciliation_persists_updated_state(tmp_path: Path) -> None:
    store = BybitPendingEntryStore(tmp_path / "pending.json")
    broker, client = _broker(pending_entry_store=store)
    _submit(broker)
    client.get_open_orders.return_value = _query_response(_order_item("New"))

    broker.get_entry_order(ORDER_LINK_ID)

    loaded = store.load()
    assert loaded is not None
    assert loaded.pending_entry.status == PendingEntryStatus.WORKING


def test_partial_fill_is_persisted_before_cancel_requested(tmp_path: Path) -> None:
    store = RecordingStore(tmp_path / "pending.json")
    broker, client = _broker(pending_entry_store=store)
    _submit(broker)
    store.saved_statuses.clear()
    client.get_open_orders.return_value = _query_response(
        _order_item("PartiallyFilled", filled="0.4", average_price="99.5")
    )

    broker.get_entry_order(ORDER_LINK_ID)

    assert store.saved_statuses == [
        PendingEntryStatus.PARTIALLY_FILLED,
        PendingEntryStatus.CANCEL_REQUESTED,
    ]
    loaded = store.load()
    assert loaded is not None
    assert loaded.pending_entry.status == PendingEntryStatus.CANCEL_REQUESTED
    assert loaded.pending_entry.filled_volume == 0.4
    assert loaded.pending_entry.average_fill_price == 99.5


def test_explicit_cancellation_persists_cancel_requested(tmp_path: Path) -> None:
    store = BybitPendingEntryStore(tmp_path / "pending.json")
    broker, _ = _broker(pending_entry_store=store)
    _submit(broker)

    broker.cancel_entry(ORDER_LINK_ID)

    loaded = store.load()
    assert loaded is not None
    assert loaded.pending_entry.status == PendingEntryStatus.CANCEL_REQUESTED


@pytest.mark.parametrize(
    ("status", "filled", "average_price"),
    [
        ("Filled", "1", "100"),
        ("Cancelled", "0", ""),
        ("Rejected", "0", ""),
    ],
)
def test_terminal_snapshot_clears_durable_state(
    tmp_path: Path,
    status: str,
    filled: str,
    average_price: str,
) -> None:
    path = tmp_path / "pending.json"
    store = BybitPendingEntryStore(path)
    broker, client = _broker(pending_entry_store=store)
    _submit(broker)
    client.get_open_orders.return_value = _query_response(
        _order_item(status, filled=filled, average_price=average_price)
    )

    broker.get_entry_order(ORDER_LINK_ID)

    assert broker.get_pending_entry() is None
    assert store.load() is None
    assert not path.exists()


def test_submit_persistence_failure_keeps_slot_and_prevents_duplicate_order(
    tmp_path: Path,
) -> None:
    store = FailingSaveStore(tmp_path / "pending.json")
    broker, client = _broker(pending_entry_store=store)

    with pytest.raises(BybitPendingEntryPersistenceError) as first_error:
        _submit(broker)
    with pytest.raises(BybitPendingEntryPersistenceError):
        _submit(broker)

    assert "sensitive" not in str(first_error.value)
    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.status == PendingEntryStatus.SUBMITTED
    client.place_order.assert_called_once()
    client.list_open_orders.assert_called_once()


def test_terminal_clear_failure_keeps_local_slot_blocked(tmp_path: Path) -> None:
    path = tmp_path / "pending.json"
    working_store = BybitPendingEntryStore(path)
    broker, client = _broker(pending_entry_store=working_store)
    _submit(broker)
    broker._pending_entry_store = FailingClearStore(path)
    client.get_open_orders.return_value = _query_response(
        _order_item("Filled", filled="1", average_price="100")
    )

    with pytest.raises(BybitPendingEntryPersistenceError):
        broker.get_entry_order(ORDER_LINK_ID)

    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.status == PendingEntryStatus.FILLED
    assert path.exists()


def test_recovery_matrix_a_no_state_and_no_orders_returns_none(tmp_path: Path) -> None:
    store = BybitPendingEntryStore(tmp_path / "pending.json")
    broker, _ = _broker(pending_entry_store=store)

    assert broker.recover_pending_entry() is None
    assert broker.get_pending_entry() is None


def test_recovery_matrix_b_orphaned_owned_order_fails_closed(tmp_path: Path) -> None:
    store = BybitPendingEntryStore(tmp_path / "pending.json")
    broker, client = _broker(pending_entry_store=store)
    client.list_open_orders.return_value = _query_response(_order_item("New"))

    with pytest.raises(BybitPendingEntryRecoveryError, match="orphaned"):
        broker.recover_pending_entry()

    client.cancel_order.assert_not_called()


@pytest.mark.parametrize("order_link_id", ["manual-order", "", None])
def test_recovery_matrix_c_foreign_or_missing_link_id_blocks(
    tmp_path: Path,
    order_link_id: str | None,
) -> None:
    store = BybitPendingEntryStore(tmp_path / "pending.json")
    broker, client = _broker(pending_entry_store=store)
    item = _order_item("New", order_link_id=order_link_id or "")
    if order_link_id is None:
        item.pop("orderLinkId")
    client.list_open_orders.return_value = _query_response(item)

    with pytest.raises(BybitActiveOrderConflictError, match="foreign"):
        broker.recover_pending_entry()

    client.cancel_order.assert_not_called()


def test_recovery_matrix_d_matching_active_order_restores_and_reconciles(
    tmp_path: Path,
) -> None:
    store = _saved_store(tmp_path)
    broker, client = _broker(pending_entry_store=store)
    client.list_open_orders.return_value = _query_response(
        _order_item("New") | {"symbol": "BTCUSDT", "category": "linear"}
    )

    recovered = broker.recover_pending_entry()

    assert recovered is not None
    assert recovered.status == PendingEntryStatus.WORKING
    assert recovered.setup_key == "stable-setup-key"
    assert recovered.signal_timestamp == SIGNAL_TIMESTAMP
    assert recovered.completed_candles_active == 2
    loaded = store.load()
    assert loaded is not None
    assert loaded.pending_entry.status == PendingEntryStatus.WORKING
    assert loaded.last_aged_candle_timestamp == LAST_AGED


def test_recovery_matrix_e_mismatched_owned_order_preserves_durable_state(
    tmp_path: Path,
) -> None:
    store = _saved_store(tmp_path)
    broker, client = _broker(pending_entry_store=store)
    client.list_open_orders.return_value = _query_response(
        _order_item("New", order_link_id=OTHER_ORDER_LINK_ID)
    )

    with pytest.raises(BybitPendingEntryRecoveryError, match="does not match"):
        broker.recover_pending_entry()

    loaded = store.load()
    assert loaded is not None
    assert loaded.pending_entry.order_link_id == ORDER_LINK_ID


def test_recovery_matrix_f_multiple_owned_orders_fail_closed(tmp_path: Path) -> None:
    store = _saved_store(tmp_path)
    broker, client = _broker(pending_entry_store=store)
    client.list_open_orders.return_value = _query_response(
        _order_item("New"),
        _order_item(
            "New",
            order_link_id=OTHER_ORDER_LINK_ID,
            order_id="exchange-order-2",
        ),
    )

    with pytest.raises(BybitActiveOrderConflictError, match="Multiple"):
        broker.recover_pending_entry()

    assert store.load() is not None


@pytest.mark.parametrize(
    ("status", "filled", "average_price"),
    [
        ("Filled", "1", "100"),
        ("Cancelled", "0", ""),
        ("Rejected", "0", ""),
    ],
)
def test_recovery_matrix_g_history_terminal_clears_state(
    tmp_path: Path,
    status: str,
    filled: str,
    average_price: str,
) -> None:
    store = _saved_store(tmp_path)
    broker, client = _broker(pending_entry_store=store)
    client.get_order_history.return_value = _query_response(
        _order_item(status, filled=filled, average_price=average_price)
    )

    assert broker.recover_pending_entry() is None
    assert broker.get_pending_entry() is None
    assert store.load() is None


def test_recovery_matrix_g_missing_exact_order_keeps_durable_state(
    tmp_path: Path,
) -> None:
    store = _saved_store(tmp_path)
    broker, _ = _broker(pending_entry_store=store)

    with pytest.raises(BybitPendingEntryRecoveryError, match="missing"):
        broker.recover_pending_entry()

    assert broker.get_pending_entry() is not None
    assert store.load() is not None


def test_recovery_matrix_h_active_order_plus_position_is_ambiguous(
    tmp_path: Path,
) -> None:
    store = _saved_store(tmp_path)
    broker, client = _broker(pending_entry_store=store)
    client.list_open_orders.return_value = _query_response(_order_item("New"))
    client.get_positions.return_value = {
        "retCode": 0,
        "result": {
            "list": [
                {
                    "size": "1",
                    "side": "Buy",
                    "positionIdx": "0",
                    "symbol": "BTCUSDT",
                    "avgPrice": "100",
                    "stopLoss": "95",
                    "takeProfit": "110",
                }
            ]
        },
    }

    with pytest.raises(BybitPendingEntryRecoveryError, match="ambiguous"):
        broker.recover_pending_entry()

    assert store.load() is not None


def test_history_fill_clears_pending_without_touching_open_position(
    tmp_path: Path,
) -> None:
    store = _saved_store(tmp_path)
    broker, client = _broker(pending_entry_store=store)
    client.get_order_history.return_value = _query_response(
        _order_item("Filled", filled="1", average_price="100")
    )
    client.get_positions.return_value = {"retCode": 0, "result": {"list": [{}]}}

    assert broker.recover_pending_entry() is None
    client.get_positions.assert_not_called()
    assert store.load() is None


def test_recovery_transport_or_malformed_listing_preserves_durable_state(
    tmp_path: Path,
) -> None:
    store = _saved_store(tmp_path)
    broker, client = _broker(pending_entry_store=store)
    client.list_open_orders.side_effect = RuntimeError(
        "signed-url-with-secret-token"
    )

    with pytest.raises(BybitActiveOrderConflictError) as error:
        broker.recover_pending_entry()

    assert "secret" not in str(error.value)
    assert store.load() is not None


def test_malformed_active_order_listing_preserves_durable_state(
    tmp_path: Path,
) -> None:
    store = _saved_store(tmp_path)
    broker, client = _broker(pending_entry_store=store)
    client.list_open_orders.return_value = ["raw", "response"]

    with pytest.raises(BybitActiveOrderConflictError, match="malformed"):
        broker.recover_pending_entry()

    assert store.load() is not None


@pytest.mark.parametrize("failure", ["transport", "malformed"])
def test_exact_recovery_lookup_failure_preserves_durable_state(
    tmp_path: Path,
    failure: str,
) -> None:
    store = _saved_store(tmp_path)
    broker, client = _broker(pending_entry_store=store)
    if failure == "transport":
        client.get_order_history.side_effect = RuntimeError(
            "signed-url-with-secret-token"
        )
    else:
        client.get_order_history.return_value = {
            "retCode": 0,
            "result": {"list": "not-a-list"},
        }

    with pytest.raises(BybitPendingEntryRecoveryError) as error:
        broker.recover_pending_entry()

    assert "secret" not in str(error.value)
    assert broker.get_pending_entry() is not None
    assert store.load() is not None


def test_matching_active_recovery_is_idempotent(tmp_path: Path) -> None:
    store = _saved_store(tmp_path)
    broker, client = _broker(pending_entry_store=store)
    client.list_open_orders.return_value = _query_response(_order_item("New"))

    first = broker.recover_pending_entry()
    second = broker.recover_pending_entry()

    assert first == second
    assert second is not None
    assert second.status == PendingEntryStatus.WORKING


@pytest.mark.parametrize(
    "active_items",
    [
        (_order_item("New", order_link_id="manual-order"),),
        (_order_item("New"),),
        (
            _order_item("New"),
            _order_item(
                "New",
                order_link_id="manual-order",
                order_id="manual-exchange-order",
            ),
        ),
    ],
)
def test_foreign_or_orphaned_owned_order_blocks_new_submission(
    tmp_path: Path,
    active_items: tuple[dict[str, object], ...],
) -> None:
    store = BybitPendingEntryStore(tmp_path / "pending.json")
    broker, client = _broker(pending_entry_store=store)
    client.list_open_orders.return_value = _query_response(*active_items)

    with pytest.raises(BybitActiveOrderConflictError):
        _submit(broker)

    client.place_order.assert_not_called()


def test_no_active_exchange_orders_allows_submission(tmp_path: Path) -> None:
    store = BybitPendingEntryStore(tmp_path / "pending.json")
    broker, client = _broker(pending_entry_store=store)

    _submit(broker)

    client.list_open_orders.assert_called_once()
    client.place_order.assert_called_once()


def test_local_identical_duplicate_skips_exchange_conflict_listing(
    tmp_path: Path,
) -> None:
    store = BybitPendingEntryStore(tmp_path / "pending.json")
    broker, client = _broker(pending_entry_store=store)
    _submit(broker)
    client.list_open_orders.reset_mock()
    client.list_open_orders.return_value = _query_response(
        _order_item("New", order_link_id="manual-order")
    )

    _submit(broker)

    client.list_open_orders.assert_not_called()
    client.place_order.assert_called_once()
