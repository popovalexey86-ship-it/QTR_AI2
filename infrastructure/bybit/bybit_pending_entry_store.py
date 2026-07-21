from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

from core.decision import Decision
from core.exceptions import BrokerError
from core.pending_entry import PendingEntry, PendingEntryStatus
from core.setup import Setup
from core.trade_request import TradeRequest
from core.trend import Trend


SCHEMA_VERSION = 1

_PERSISTABLE_STATUSES = frozenset(
    {
        PendingEntryStatus.SUBMITTED,
        PendingEntryStatus.WORKING,
        PendingEntryStatus.PARTIALLY_FILLED,
        PendingEntryStatus.CANCEL_REQUESTED,
    }
)

_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "order_link_id",
        "exchange_order_id",
        "setup_key",
        "request",
        "signal_timestamp",
        "status",
        "completed_candles_active",
        "filled_volume",
        "average_fill_price",
        "last_aged_candle_timestamp",
    }
)

_REQUEST_FIELDS = frozenset(
    {
        "symbol",
        "decision",
        "entry",
        "stop_loss",
        "take_profit",
        "volume",
    }
)


class BybitPendingEntryStoreError(BrokerError):
    """Raised when durable pending-entry state cannot be trusted."""


@dataclass(frozen=True, slots=True)
class PersistedBybitPendingEntry:
    schema_version: int
    pending_entry: PendingEntry
    last_aged_candle_timestamp: datetime | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != SCHEMA_VERSION
        ):
            raise ValueError("Unsupported pending-entry schema version.")
        if self.pending_entry.status not in _PERSISTABLE_STATUSES:
            raise ValueError("Terminal pending-entry state cannot be persisted.")
        if self.last_aged_candle_timestamp is not None:
            _validate_utc_timestamp(self.last_aged_candle_timestamp)


class BybitPendingEntryStore:
    """Atomic UTF-8 JSON storage for one active Bybit pending entry."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> PersistedBybitPendingEntry | None:
        if not self._path.exists():
            return None
        try:
            with self._path.open("r", encoding="utf-8") as state_file:
                raw_state = json.load(state_file)
            return _decode_state(raw_state)
        except BybitPendingEntryStoreError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
            raise BybitPendingEntryStoreError(
                "Durable Bybit pending-entry state is invalid or unreadable."
            ) from None

    def save(self, state: PersistedBybitPendingEntry) -> None:
        if not isinstance(state, PersistedBybitPendingEntry):
            raise BybitPendingEntryStoreError(
                "Durable Bybit pending-entry state is invalid."
            )
        try:
            payload = _encode_state(state)
        except (TypeError, ValueError):
            raise BybitPendingEntryStoreError(
                "Durable Bybit pending-entry state is invalid."
            ) from None

        temporary_path: Path | None = None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(
                    payload,
                    temporary_file,
                    ensure_ascii=True,
                    allow_nan=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self._path)
            temporary_path = None
        except (OSError, TypeError, ValueError):
            raise BybitPendingEntryStoreError(
                "Failed to persist durable Bybit pending-entry state."
            ) from None
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def clear(self) -> None:
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            raise BybitPendingEntryStoreError(
                "Failed to clear durable Bybit pending-entry state."
            ) from None


def _encode_state(state: PersistedBybitPendingEntry) -> dict[str, object]:
    entry = state.pending_entry
    validated = PersistedBybitPendingEntry(
        schema_version=state.schema_version,
        pending_entry=entry,
        last_aged_candle_timestamp=state.last_aged_candle_timestamp,
    )
    request = entry.request
    if not isinstance(entry.order_link_id, str) or not entry.order_link_id.strip():
        raise ValueError("Persisted order link ID is invalid.")
    if not isinstance(entry.setup_key, str) or not entry.setup_key.strip():
        raise ValueError("Persisted setup key is invalid.")
    if (
        entry.exchange_order_id is not None
        and (
            not isinstance(entry.exchange_order_id, str)
            or not entry.exchange_order_id.strip()
        )
    ):
        raise ValueError("Persisted exchange order ID is invalid.")
    if not isinstance(request.symbol, str) or not request.symbol.strip():
        raise ValueError("Persisted request symbol is invalid.")
    _validate_positive_finite(request.entry, "entry")
    _validate_positive_finite(request.stop_loss, "stop loss")
    _validate_positive_finite(request.take_profit, "take profit")
    _validate_positive_finite(request.volume, "volume")
    if request.decision not in (Decision.BUY, Decision.SELL):
        raise ValueError("Persisted request direction must be BUY or SELL.")
    if (
        isinstance(entry.completed_candles_active, bool)
        or not isinstance(entry.completed_candles_active, int)
        or entry.completed_candles_active < 0
    ):
        raise ValueError("Persisted completed candle count is invalid.")
    _validate_non_negative_number(entry.filled_volume, "filled volume")
    if entry.average_fill_price is not None:
        _validate_positive_finite(entry.average_fill_price, "average fill price")
    _validate_utc_timestamp(entry.signal_timestamp)

    return {
        "schema_version": validated.schema_version,
        "order_link_id": entry.order_link_id,
        "exchange_order_id": entry.exchange_order_id,
        "setup_key": entry.setup_key,
        "request": {
            "symbol": request.symbol,
            "decision": request.decision.value,
            "entry": request.entry,
            "stop_loss": request.stop_loss,
            "take_profit": request.take_profit,
            "volume": request.volume,
        },
        "signal_timestamp": _format_utc_timestamp(entry.signal_timestamp),
        "status": entry.status.value,
        "completed_candles_active": entry.completed_candles_active,
        "filled_volume": entry.filled_volume,
        "average_fill_price": entry.average_fill_price,
        "last_aged_candle_timestamp": (
            _format_utc_timestamp(validated.last_aged_candle_timestamp)
            if validated.last_aged_candle_timestamp is not None
            else None
        ),
    }


def _decode_state(raw_state: object) -> PersistedBybitPendingEntry:
    state = _require_mapping(raw_state, "state")
    _require_exact_fields(state, _TOP_LEVEL_FIELDS)

    schema_version = _require_int(state, "schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ValueError("Unsupported schema version.")

    request_state = _require_mapping(state.get("request"), "request")
    _require_exact_fields(request_state, _REQUEST_FIELDS)
    decision_text = _require_string(request_state, "decision")
    try:
        decision = Decision(decision_text)
    except ValueError:
        raise ValueError("Invalid persisted decision.") from None
    if decision not in (Decision.BUY, Decision.SELL):
        raise ValueError("Persisted decision must be BUY or SELL.")

    entry_price = _require_positive_finite(request_state, "entry")
    stop_loss = _require_positive_finite(request_state, "stop_loss")
    take_profit = _require_positive_finite(request_state, "take_profit")
    volume = _require_positive_finite(request_state, "volume")
    signal_timestamp = _parse_utc_timestamp(
        _require_string(state, "signal_timestamp")
    )
    status_text = _require_string(state, "status")
    try:
        status = PendingEntryStatus(status_text)
    except ValueError:
        raise ValueError("Invalid persisted pending-entry status.") from None
    if status not in _PERSISTABLE_STATUSES:
        raise ValueError("Terminal pending-entry state cannot be loaded.")

    setup = Setup(
        index=0,
        timestamp=signal_timestamp,
        trend=(Trend.BULLISH if decision == Decision.BUY else Trend.BEARISH),
        entry=entry_price,
        stop_loss=stop_loss,
    )
    request = TradeRequest(
        symbol=_require_string(request_state, "symbol"),
        decision=decision,
        entry=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        volume=volume,
        setup=setup,
    )

    exchange_order_id_value = state.get("exchange_order_id")
    if exchange_order_id_value is not None and not isinstance(
        exchange_order_id_value,
        str,
    ):
        raise ValueError("Invalid exchange order ID.")
    if isinstance(exchange_order_id_value, str) and not exchange_order_id_value.strip():
        raise ValueError("Invalid exchange order ID.")

    completed_candles_active = _require_int(
        state,
        "completed_candles_active",
    )
    if completed_candles_active < 0:
        raise ValueError("Invalid completed candle count.")
    filled_volume = _require_non_negative_finite(state, "filled_volume")
    average_fill_price = _require_optional_positive_finite(
        state,
        "average_fill_price",
    )
    last_aged_value = state.get("last_aged_candle_timestamp")
    if last_aged_value is None:
        last_aged_timestamp = None
    elif isinstance(last_aged_value, str):
        last_aged_timestamp = _parse_utc_timestamp(last_aged_value)
    else:
        raise ValueError("Invalid last-aged candle timestamp.")

    pending_entry = PendingEntry(
        order_link_id=_require_string(state, "order_link_id"),
        exchange_order_id=(
            exchange_order_id_value.strip()
            if isinstance(exchange_order_id_value, str)
            else None
        ),
        setup_key=_require_string(state, "setup_key"),
        request=request,
        signal_timestamp=signal_timestamp,
        status=status,
        completed_candles_active=completed_candles_active,
        filled_volume=filled_volume,
        average_fill_price=average_fill_price,
    )
    return PersistedBybitPendingEntry(
        schema_version=schema_version,
        pending_entry=pending_entry,
        last_aged_candle_timestamp=last_aged_timestamp,
    )


def _require_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) for key in value
    ):
        raise ValueError(f"Persisted {field_name} must be an object.")
    return value


def _require_exact_fields(
    value: Mapping[str, Any],
    expected_fields: frozenset[str],
) -> None:
    if set(value) != expected_fields:
        raise ValueError("Persisted state fields do not match the schema.")


def _require_string(value: Mapping[str, Any], field_name: str) -> str:
    field = value.get(field_name)
    if not isinstance(field, str) or not field.strip():
        raise ValueError(f"Persisted {field_name} must be a non-empty string.")
    return field.strip()


def _require_int(value: Mapping[str, Any], field_name: str) -> int:
    field = value.get(field_name)
    if isinstance(field, bool) or not isinstance(field, int):
        raise ValueError(f"Persisted {field_name} must be an integer.")
    return field


def _require_number(value: Mapping[str, Any], field_name: str) -> float:
    field = value.get(field_name)
    if isinstance(field, bool) or not isinstance(field, (int, float)):
        raise ValueError(f"Persisted {field_name} must be numeric.")
    number = float(field)
    if not math.isfinite(number):
        raise ValueError(f"Persisted {field_name} must be finite.")
    return number


def _require_positive_finite(
    value: Mapping[str, Any],
    field_name: str,
) -> float:
    number = _require_number(value, field_name)
    _validate_positive_finite(number, field_name)
    return number


def _require_non_negative_finite(
    value: Mapping[str, Any],
    field_name: str,
) -> float:
    number = _require_number(value, field_name)
    if number < 0:
        raise ValueError(f"Persisted {field_name} cannot be negative.")
    return number


def _require_optional_positive_finite(
    value: Mapping[str, Any],
    field_name: str,
) -> float | None:
    if value.get(field_name) is None:
        return None
    return _require_positive_finite(value, field_name)


def _validate_positive_finite(value: object, field_name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"Persisted {field_name} must be finite and positive.")


def _validate_non_negative_number(value: object, field_name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(
            f"Persisted {field_name} must be finite and non-negative."
        )


def _parse_utc_timestamp(value: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("Persisted timestamp is not valid ISO-8601.") from None
    _validate_utc_timestamp(timestamp)
    return timestamp.astimezone(UTC)


def _validate_utc_timestamp(value: datetime) -> None:
    if not isinstance(value, datetime):
        raise ValueError("Persisted timestamps must be datetime values.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Persisted timestamps must be timezone-aware UTC.")
    if value.utcoffset() != timedelta(0):
        raise ValueError("Persisted timestamps must use UTC.")


def _format_utc_timestamp(value: datetime) -> str:
    _validate_utc_timestamp(value)
    return value.astimezone(UTC).isoformat()
