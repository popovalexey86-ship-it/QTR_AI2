from pathlib import Path

import pytest

from core.pending_entry import PendingEntryStatus
from core.pending_entry_event import PendingEntryEventKind
from infrastructure.bybit.bybit_broker import BybitPendingEntryPersistenceError
from infrastructure.bybit.bybit_pending_entry_store import BybitPendingEntryStore
from tests.test_bybit_pending_broker import (
    ORDER_LINK_ID,
    _broker,
    _order_item,
    _query_response,
    _submit,
)
from tests.test_bybit_pending_recovery import FailingSaveStore, _saved_store
from tests.test_bybit_pending_ttl import CANDLES


def _persistent_broker(tmp_path: Path):
    store = BybitPendingEntryStore(tmp_path / "pending.json")
    return (*_broker(pending_entry_store=store), store)


def test_submission_event_and_drain_once(tmp_path: Path) -> None:
    broker, _, _ = _persistent_broker(tmp_path)

    _submit(broker)
    events = broker.drain_pending_entry_events()

    assert len(events) == 1
    assert events[0].kind == PendingEntryEventKind.SUBMITTED
    assert events[0].status == PendingEntryStatus.SUBMITTED
    assert events[0].symbol == "BTCUSDT"
    assert broker.drain_pending_entry_events() == ()


def test_working_event_but_no_repeated_or_stale_event(tmp_path: Path) -> None:
    broker, client, _ = _persistent_broker(tmp_path)
    _submit(broker)
    broker.drain_pending_entry_events()
    client.get_open_orders.return_value = _query_response(_order_item("New"))

    broker.get_entry_order(ORDER_LINK_ID)
    working = broker.drain_pending_entry_events()
    broker.get_entry_order(ORDER_LINK_ID)
    repeated = broker.drain_pending_entry_events()
    client.get_open_orders.return_value = _query_response(_order_item("Created"))
    broker.get_entry_order(ORDER_LINK_ID)

    assert [event.status for event in working] == [PendingEntryStatus.WORKING]
    assert repeated == ()
    assert broker.drain_pending_entry_events() == ()


def test_partial_fill_emits_fill_then_cancellation_requested(tmp_path: Path) -> None:
    broker, client, _ = _persistent_broker(tmp_path)
    _submit(broker)
    broker.drain_pending_entry_events()
    client.get_open_orders.return_value = _query_response(
        _order_item("PartiallyFilled", filled="0.4", average_price="99.5")
    )

    broker.get_entry_order(ORDER_LINK_ID)
    events = broker.drain_pending_entry_events()

    assert [event.status for event in events] == [
        PendingEntryStatus.PARTIALLY_FILLED,
        PendingEntryStatus.CANCEL_REQUESTED,
    ]
    assert events[0].filled_volume == 0.4
    assert events[0].average_fill_price == 99.5


def test_duplicate_cancel_emits_one_status_event(tmp_path: Path) -> None:
    broker, _, _ = _persistent_broker(tmp_path)
    _submit(broker)
    broker.drain_pending_entry_events()

    broker.cancel_entry(ORDER_LINK_ID)
    broker.cancel_entry(ORDER_LINK_ID)

    events = broker.drain_pending_entry_events()
    assert [event.status for event in events] == [
        PendingEntryStatus.CANCEL_REQUESTED
    ]


@pytest.mark.parametrize(
    ("exchange_status", "domain_status", "filled", "average", "reason"),
    [
        ("Filled", PendingEntryStatus.FILLED, "1", "100", "EC_NoError"),
        ("Cancelled", PendingEntryStatus.CANCELLED, "0", "", "EC_NoError"),
        ("Rejected", PendingEntryStatus.REJECTED, "0", "", "  safe\nreason  "),
    ],
)
def test_terminal_event_survives_slot_clearing(
    tmp_path: Path,
    exchange_status: str,
    domain_status: PendingEntryStatus,
    filled: str,
    average: str,
    reason: str,
) -> None:
    broker, client, _ = _persistent_broker(tmp_path)
    _submit(broker)
    broker.drain_pending_entry_events()
    client.get_open_orders.return_value = _query_response(
        _order_item(
            exchange_status,
            filled=filled,
            average_price=average,
            rejection_reason=reason,
        )
    )

    broker.get_entry_order(ORDER_LINK_ID)
    events = broker.drain_pending_entry_events()

    assert broker.get_pending_entry() is None
    assert len(events) == 1
    assert events[0].kind == PendingEntryEventKind.TERMINAL
    assert events[0].status == domain_status
    if domain_status == PendingEntryStatus.REJECTED:
        assert events[0].rejection_reason == "safe reason"


def test_expired_terminal_event(tmp_path: Path) -> None:
    broker, client, _ = _persistent_broker(tmp_path)
    _submit(broker)
    broker.drain_pending_entry_events()
    client.get_open_orders.return_value = _query_response(_order_item("New"))
    broker.age_pending_entry(CANDLES[:4], ttl_candles=4)
    broker.drain_pending_entry_events()
    client.get_open_orders.return_value = _query_response(_order_item("Cancelled"))

    broker.get_entry_order(ORDER_LINK_ID)
    events = broker.drain_pending_entry_events()

    assert len(events) == 1
    assert events[0].status == PendingEntryStatus.EXPIRED
    assert events[0].kind == PendingEntryEventKind.TERMINAL


def test_persistence_failure_emits_no_event(tmp_path: Path) -> None:
    broker, _ = _broker(
        pending_entry_store=FailingSaveStore(tmp_path / "pending.json")
    )

    with pytest.raises(BybitPendingEntryPersistenceError):
        _submit(broker)

    assert broker.drain_pending_entry_events() == ()


def test_active_recovery_emits_once_without_intermediate_replay(tmp_path: Path) -> None:
    store = _saved_store(tmp_path)
    broker, client = _broker(pending_entry_store=store)
    client.list_open_orders.return_value = _query_response(_order_item("New"))

    broker.recover_pending_entry()
    first = broker.drain_pending_entry_events()
    broker.recover_pending_entry()

    assert len(first) == 1
    assert first[0].kind == PendingEntryEventKind.RECOVERED
    assert first[0].status == PendingEntryStatus.WORKING
    assert broker.drain_pending_entry_events() == ()


def test_terminal_recovery_emits_only_terminal_event(tmp_path: Path) -> None:
    store = _saved_store(tmp_path)
    broker, client = _broker(pending_entry_store=store)
    client.get_order_history.return_value = _query_response(
        _order_item("Filled", filled="1", average_price="100")
    )

    broker.recover_pending_entry()
    events = broker.drain_pending_entry_events()

    assert len(events) == 1
    assert events[0].kind == PendingEntryEventKind.TERMINAL
    assert events[0].status == PendingEntryStatus.FILLED


def test_cancel_fill_race_emits_meaningful_final_transition(tmp_path: Path) -> None:
    broker, client, _ = _persistent_broker(tmp_path)
    _submit(broker)
    broker.drain_pending_entry_events()
    broker.cancel_entry(ORDER_LINK_ID)
    broker.drain_pending_entry_events()
    client.get_open_orders.return_value = _query_response(
        _order_item("Filled", filled="1", average_price="100")
    )

    broker.get_entry_order(ORDER_LINK_ID)
    events = broker.drain_pending_entry_events()

    assert [event.status for event in events] == [PendingEntryStatus.FILLED]
