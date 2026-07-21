from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

import pytest

from core.decision import Decision
from core.pending_entry import PendingEntry, PendingEntryStatus
from core.setup import Setup
from core.trade_request import TradeRequest
from core.trend import Trend
import infrastructure.bybit.bybit_pending_entry_store as store_module
from infrastructure.bybit.bybit_pending_entry_store import (
    SCHEMA_VERSION,
    BybitPendingEntryStore,
    BybitPendingEntryStoreError,
    PersistedBybitPendingEntry,
)


SIGNAL_TIMESTAMP = datetime(2026, 2, 3, 4, 5, 6, tzinfo=UTC)
LAST_AGED_TIMESTAMP = datetime(2026, 2, 3, 4, 10, tzinfo=UTC)


def _request(decision: Decision = Decision.BUY) -> TradeRequest:
    bullish = decision == Decision.BUY
    entry = 100.0
    stop_loss = 95.0 if bullish else 105.0
    take_profit = 110.0 if bullish else 90.0
    return TradeRequest(
        symbol="BTCUSDT",
        decision=decision,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        volume=1.25,
        setup=Setup(
            index=7,
            timestamp=SIGNAL_TIMESTAMP - timedelta(minutes=5),
            trend=Trend.BULLISH if bullish else Trend.BEARISH,
            entry=entry,
            stop_loss=stop_loss,
        ),
    )


def _state(
    *,
    decision: Decision = Decision.BUY,
    status: PendingEntryStatus = PendingEntryStatus.WORKING,
    filled_volume: float = 0.0,
    average_fill_price: float | None = None,
) -> PersistedBybitPendingEntry:
    return PersistedBybitPendingEntry(
        schema_version=SCHEMA_VERSION,
        pending_entry=PendingEntry(
            order_link_id="QTR-0123456789abcdef",
            exchange_order_id="exchange-order-1",
            setup_key="stable-setup-key",
            request=_request(decision),
            signal_timestamp=SIGNAL_TIMESTAMP,
            status=status,
            completed_candles_active=3,
            filled_volume=filled_volume,
            average_fill_price=average_fill_price,
        ),
        last_aged_candle_timestamp=LAST_AGED_TIMESTAMP,
    )


@pytest.mark.parametrize("decision", [Decision.BUY, Decision.SELL])
def test_save_load_round_trip_preserves_actionable_request(
    tmp_path: Path,
    decision: Decision,
) -> None:
    store = BybitPendingEntryStore(tmp_path / "state.json")

    store.save(_state(decision=decision))
    loaded = store.load()

    assert loaded is not None
    assert loaded.schema_version == 1
    assert loaded.pending_entry.order_link_id == "QTR-0123456789abcdef"
    assert loaded.pending_entry.exchange_order_id == "exchange-order-1"
    assert loaded.pending_entry.setup_key == "stable-setup-key"
    assert loaded.pending_entry.request.symbol == "BTCUSDT"
    assert loaded.pending_entry.request.decision == decision
    assert loaded.pending_entry.request.entry == 100.0
    assert loaded.pending_entry.request.stop_loss == (
        95.0 if decision == Decision.BUY else 105.0
    )
    assert loaded.pending_entry.request.take_profit == (
        110.0 if decision == Decision.BUY else 90.0
    )
    assert loaded.pending_entry.request.volume == 1.25
    assert loaded.pending_entry.completed_candles_active == 3


def test_utc_timestamps_and_partial_fill_are_preserved(tmp_path: Path) -> None:
    store = BybitPendingEntryStore(tmp_path / "state.json")
    state = _state(
        status=PendingEntryStatus.PARTIALLY_FILLED,
        filled_volume=0.5,
        average_fill_price=99.75,
    )

    store.save(state)
    loaded = store.load()

    assert loaded is not None
    assert loaded.pending_entry.signal_timestamp == SIGNAL_TIMESTAMP
    assert loaded.pending_entry.signal_timestamp.tzinfo is UTC
    assert loaded.last_aged_candle_timestamp == LAST_AGED_TIMESTAMP
    assert loaded.pending_entry.status == PendingEntryStatus.PARTIALLY_FILLED
    assert loaded.pending_entry.filled_volume == 0.5
    assert loaded.pending_entry.average_fill_price == 99.75


def test_cancel_requested_state_round_trips(tmp_path: Path) -> None:
    store = BybitPendingEntryStore(tmp_path / "state.json")
    store.save(_state(status=PendingEntryStatus.CANCEL_REQUESTED))

    loaded = store.load()

    assert loaded is not None
    assert loaded.pending_entry.status == PendingEntryStatus.CANCEL_REQUESTED


def test_clear_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    store = BybitPendingEntryStore(path)
    store.save(_state())

    store.clear()
    store.clear()

    assert not path.exists()
    assert store.load() is None


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "runtime" / "state.json"
    store = BybitPendingEntryStore(path)

    store.save(_state())

    assert path.is_file()


def test_save_atomically_replaces_destination_in_same_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "state.json"
    store = BybitPendingEntryStore(path)
    replacements: list[tuple[Path, Path]] = []
    real_replace = store_module.os.replace

    def recording_replace(source: str | Path, destination: str | Path) -> None:
        replacements.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(store_module.os, "replace", recording_replace)

    store.save(_state())

    assert len(replacements) == 1
    temporary_path, destination = replacements[0]
    assert temporary_path.parent == path.parent
    assert destination == path
    assert not temporary_path.exists()


def _write_payload(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, allow_nan=True), encoding="utf-8")


@pytest.mark.parametrize(
    "raw_text",
    ["{", "[]", "null", "not-json"],
)
def test_malformed_json_fails_closed(tmp_path: Path, raw_text: str) -> None:
    path = tmp_path / "state.json"
    path.write_text(raw_text, encoding="utf-8")

    with pytest.raises(BybitPendingEntryStoreError) as error:
        BybitPendingEntryStore(path).load()

    assert raw_text not in str(error.value)


def test_wrong_schema_version_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    store = BybitPendingEntryStore(path)
    store.save(_state())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["schema_version"] = 2
    _write_payload(path, payload)

    with pytest.raises(BybitPendingEntryStoreError, match="invalid"):
        store.load()


@pytest.mark.parametrize("mutation", ["missing", "extra", "request_missing"])
def test_schema_fields_are_strict(tmp_path: Path, mutation: str) -> None:
    path = tmp_path / "state.json"
    store = BybitPendingEntryStore(path)
    store.save(_state())
    payload = json.loads(path.read_text(encoding="utf-8"))
    if mutation == "missing":
        del payload["setup_key"]
    elif mutation == "extra":
        payload["raw_response"] = {"secret": "do-not-load"}
    else:
        del payload["request"]["volume"]
    _write_payload(path, payload)

    with pytest.raises(BybitPendingEntryStoreError):
        store.load()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "unknown"),
        ("signal_timestamp", "2026-01-01T00:00:00"),
        ("signal_timestamp", "2026-01-01T03:00:00+03:00"),
        ("filled_volume", float("nan")),
        ("filled_volume", float("inf")),
    ],
)
def test_invalid_enum_timestamp_or_number_fails_closed(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    path = tmp_path / "state.json"
    store = BybitPendingEntryStore(path)
    store.save(_state())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    _write_payload(path, payload)

    with pytest.raises(BybitPendingEntryStoreError):
        store.load()


@pytest.mark.parametrize("field", ["entry", "stop_loss", "take_profit", "volume"])
def test_non_finite_request_number_fails_closed(
    tmp_path: Path,
    field: str,
) -> None:
    path = tmp_path / "state.json"
    store = BybitPendingEntryStore(path)
    store.save(_state())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["request"][field] = float("nan")
    _write_payload(path, payload)

    with pytest.raises(BybitPendingEntryStoreError):
        store.load()


@pytest.mark.parametrize("terminal", ["filled", "cancelled", "rejected", "expired"])
def test_terminal_state_is_rejected_on_load(
    tmp_path: Path,
    terminal: str,
) -> None:
    path = tmp_path / "state.json"
    store = BybitPendingEntryStore(path)
    store.save(_state())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["status"] = terminal
    if terminal == "filled":
        payload["filled_volume"] = 1.25
        payload["average_fill_price"] = 100.0
    _write_payload(path, payload)

    with pytest.raises(BybitPendingEntryStoreError):
        store.load()


def test_model_rejects_terminal_state_before_save() -> None:
    active = _state().pending_entry
    terminal = replace(
        active,
        status=PendingEntryStatus.FILLED,
        filled_volume=active.request.volume,
        average_fill_price=100.0,
    )

    with pytest.raises(ValueError, match="Terminal"):
        PersistedBybitPendingEntry(
            schema_version=SCHEMA_VERSION,
            pending_entry=terminal,
        )


def test_json_contains_no_credentials_or_raw_payload_fields(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = _state()

    BybitPendingEntryStore(path).save(state)
    text = path.read_text(encoding="utf-8")

    assert "api_key" not in text
    assert "api_secret" not in text
    assert "telegram" not in text
    assert "raw_response" not in text
    assert "signed" not in text
    assert "sensitive" not in repr(state)


def test_failed_atomic_save_leaves_previous_state_readable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "state.json"
    store = BybitPendingEntryStore(path)
    original = _state(status=PendingEntryStatus.WORKING)
    store.save(original)

    def failing_replace(source: str | Path, destination: str | Path) -> None:
        raise OSError("filesystem details must not escape")

    monkeypatch.setattr(store_module.os, "replace", failing_replace)
    with pytest.raises(BybitPendingEntryStoreError) as error:
        store.save(_state(status=PendingEntryStatus.CANCEL_REQUESTED))

    assert "filesystem details" not in str(error.value)
    loaded = store.load()
    assert loaded is not None
    assert loaded.pending_entry.status == PendingEntryStatus.WORKING
    assert not tuple(tmp_path.glob("*.tmp"))
