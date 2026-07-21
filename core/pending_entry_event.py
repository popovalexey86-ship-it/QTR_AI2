from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import math

from core.decision import Decision
from core.pending_entry import PendingEntryStatus


class PendingEntryEventKind(Enum):
    SUBMITTED = "submitted"
    RECOVERED = "recovered"
    STATUS_CHANGED = "status_changed"
    TERMINAL = "terminal"


@dataclass(frozen=True, slots=True)
class PendingEntryEvent:
    kind: PendingEntryEventKind
    order_link_id: str
    exchange_order_id: str | None
    symbol: str
    decision: Decision
    status: PendingEntryStatus
    previous_status: PendingEntryStatus | None
    entry: float
    requested_volume: float
    filled_volume: float
    average_fill_price: float | None
    signal_timestamp: datetime
    rejection_reason: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _non_empty(self.order_link_id, "Order link ID")
        if self.exchange_order_id is not None:
            _non_empty(self.exchange_order_id, "Exchange order ID")
        _non_empty(self.symbol, "Symbol")
        if not self.symbol.isascii():
            raise ValueError("Pending-entry event symbol must be ASCII-safe.")
        if self.decision not in (Decision.BUY, Decision.SELL):
            raise ValueError("Pending-entry event direction must be BUY or SELL.")
        _positive_finite(self.entry, "entry")
        _positive_finite(self.requested_volume, "requested volume")
        _non_negative_finite(self.filled_volume, "filled volume")
        if self.filled_volume > self.requested_volume:
            raise ValueError("Filled volume cannot exceed requested volume.")
        if self.average_fill_price is not None:
            _positive_finite(self.average_fill_price, "average fill price")
        if self.filled_volume > 0 and self.average_fill_price is None:
            raise ValueError("A filled event requires an average fill price.")
        if self.filled_volume == 0 and self.average_fill_price is not None:
            raise ValueError("An unfilled event cannot have an average fill price.")
        if (
            self.signal_timestamp.tzinfo is None
            or self.signal_timestamp.utcoffset() is None
        ):
            raise ValueError("Pending-entry event timestamp must be timezone-aware.")
        if self.kind == PendingEntryEventKind.TERMINAL and self.status not in {
            PendingEntryStatus.FILLED,
            PendingEntryStatus.CANCELLED,
            PendingEntryStatus.EXPIRED,
            PendingEntryStatus.REJECTED,
        }:
            raise ValueError("A terminal event requires a terminal status.")
        reason = _sanitize_reason(self.rejection_reason)
        if reason is not None and self.status != PendingEntryStatus.REJECTED:
            raise ValueError("Only rejected events may include a rejection reason.")
        object.__setattr__(self, "rejection_reason", reason)


def _non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} cannot be empty.")


def _positive_finite(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"Pending-entry event {field_name} must be positive.")


def _non_negative_finite(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not math.isfinite(value) or value < 0:
        raise ValueError(
            f"Pending-entry event {field_name} must be non-negative."
        )


def _sanitize_reason(value: str | None) -> str | None:
    if value is None:
        return None
    sanitized = " ".join(
        "".join(character if character.isprintable() else " " for character in value)
        .split()
    )[:200]
    return sanitized or None
