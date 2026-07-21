from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
import hashlib
import math

from core.decision import Decision
from core.entry_fill_validation import validate_entry_fill_fields
from core.trade_request import TradeRequest


class PendingEntryStatus(Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    PARTIALLY_FILLED = "partially_filled"
    CANCEL_REQUESTED = "cancel_requested"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class InvalidPendingEntryTransition(ValueError):
    """Raised when a pending entry cannot move to the requested status."""


_ALLOWED_TRANSITIONS: dict[
    PendingEntryStatus,
    frozenset[PendingEntryStatus],
] = {
    PendingEntryStatus.SUBMITTED: frozenset(
        {
            PendingEntryStatus.WORKING,
            PendingEntryStatus.PARTIALLY_FILLED,
            PendingEntryStatus.CANCEL_REQUESTED,
            PendingEntryStatus.FILLED,
            PendingEntryStatus.CANCELLED,
            PendingEntryStatus.REJECTED,
        }
    ),
    PendingEntryStatus.WORKING: frozenset(
        {
            PendingEntryStatus.PARTIALLY_FILLED,
            PendingEntryStatus.FILLED,
            PendingEntryStatus.CANCEL_REQUESTED,
            PendingEntryStatus.CANCELLED,
            PendingEntryStatus.REJECTED,
        }
    ),
    PendingEntryStatus.PARTIALLY_FILLED: frozenset(
        {
            PendingEntryStatus.PARTIALLY_FILLED,
            PendingEntryStatus.FILLED,
            PendingEntryStatus.CANCEL_REQUESTED,
            PendingEntryStatus.CANCELLED,
            PendingEntryStatus.REJECTED,
        }
    ),
    PendingEntryStatus.CANCEL_REQUESTED: frozenset(
        {
            PendingEntryStatus.FILLED,
            PendingEntryStatus.PARTIALLY_FILLED,
            PendingEntryStatus.CANCELLED,
            PendingEntryStatus.REJECTED,
            PendingEntryStatus.EXPIRED,
        }
    ),
    PendingEntryStatus.FILLED: frozenset(),
    PendingEntryStatus.CANCELLED: frozenset(),
    PendingEntryStatus.REJECTED: frozenset(),
    PendingEntryStatus.EXPIRED: frozenset(),
}


def validate_pending_entry_transition(
    current: PendingEntryStatus,
    target: PendingEntryStatus,
) -> None:
    """Validate one exchange-independent pending-entry state transition."""

    if target not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidPendingEntryTransition(
            f"Pending entry transition {current.name} -> {target.name} "
            "is not allowed."
        )


def build_setup_key(
    *,
    symbol: str,
    direction: Decision,
    setup_timestamp: datetime,
    entry: float,
    stop_loss: float,
    take_profit: float,
) -> str:
    """Build a stable, versioned identity for an actionable setup."""

    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("Setup identity requires a non-empty symbol.")
    if direction not in (Decision.BUY, Decision.SELL):
        raise ValueError("Setup identity requires BUY or SELL direction.")
    _validate_aware_datetime(setup_timestamp)

    prices = (entry, stop_loss, take_profit)
    if any(not math.isfinite(price) for price in prices):
        raise ValueError("Setup identity prices must be finite.")

    timestamp = setup_timestamp.astimezone(UTC).isoformat(timespec="microseconds")
    payload = "|".join(
        (
            "qtr-setup-v1",
            normalized_symbol,
            direction.value,
            timestamp,
            entry.hex(),
            stop_loss.hex(),
            take_profit.hex(),
        )
    )
    return f"qtr-setup-v1:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def build_order_link_id(setup_key: str) -> str:
    """Build an ASCII-safe deterministic Bybit-compatible client order ID."""

    normalized_key = setup_key.strip()
    if not normalized_key:
        raise ValueError("Order link ID requires a non-empty setup key.")

    digest = hashlib.sha256(normalized_key.encode("utf-8")).hexdigest()
    return f"QTR-{digest[:32]}"


@dataclass(frozen=True, slots=True)
class PendingEntry:
    order_link_id: str
    setup_key: str
    request: TradeRequest
    signal_timestamp: datetime
    status: PendingEntryStatus = PendingEntryStatus.SUBMITTED
    exchange_order_id: str | None = None
    completed_candles_active: int = 0
    filled_volume: float = 0.0
    average_fill_price: float | None = None
    expiry_requested: bool = False

    def __post_init__(self) -> None:
        _validate_non_empty(self.order_link_id, "Pending entry order link ID")
        _validate_non_empty(self.setup_key, "Pending entry setup key")
        if self.exchange_order_id is not None:
            _validate_non_empty(
                self.exchange_order_id,
                "Pending entry exchange order ID",
            )
        _validate_aware_datetime(self.signal_timestamp)

        if self.completed_candles_active < 0:
            raise ValueError(
                "Completed active candle count cannot be negative."
            )
        if not isinstance(self.expiry_requested, bool):
            raise ValueError("Pending entry expiry marker must be boolean.")

        validate_entry_fill_fields(
            status_name=self.status.name,
            requested_volume=self.request.volume,
            filled_volume=self.filled_volume,
            average_fill_price=self.average_fill_price,
        )


def _validate_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty.")


def _validate_aware_datetime(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Pending entry timestamps must be timezone-aware.")
