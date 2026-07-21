from dataclasses import dataclass, field

from core.entry_fill_validation import validate_entry_fill_fields
from core.pending_entry import PendingEntryStatus


@dataclass(frozen=True, slots=True)
class EntryOrderAcknowledgement:
    """Normalized acknowledgement that an entry submission was accepted."""

    order_link_id: str
    exchange_order_id: str | None = None

    def __post_init__(self) -> None:
        _validate_id(self.order_link_id, "Order link ID")
        if self.exchange_order_id is not None:
            _validate_id(self.exchange_order_id, "Exchange order ID")


@dataclass(frozen=True, slots=True)
class EntryOrderSnapshot:
    """Exchange-independent state of one submitted entry order."""

    order_link_id: str
    exchange_order_id: str | None
    status: PendingEntryStatus
    requested_volume: float
    filled_volume: float
    average_fill_price: float | None = None
    rejection_reason: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _validate_id(self.order_link_id, "Order link ID")
        if self.exchange_order_id is not None:
            _validate_id(self.exchange_order_id, "Exchange order ID")

        validate_entry_fill_fields(
            status_name=self.status.name,
            requested_volume=self.requested_volume,
            filled_volume=self.filled_volume,
            average_fill_price=self.average_fill_price,
        )
        normalized_reason = _normalize_rejection_reason(
            self.status,
            self.rejection_reason,
        )
        object.__setattr__(self, "rejection_reason", normalized_reason)


def _validate_id(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty.")


def _normalize_rejection_reason(
    status: PendingEntryStatus,
    rejection_reason: str | None,
) -> str | None:
    if rejection_reason is None:
        return None
    if status != PendingEntryStatus.REJECTED:
        raise ValueError("Only a rejected order may have a rejection reason.")

    reason = rejection_reason.strip()
    if (
        not reason
        or len(reason) > 200
        or not reason.isprintable()
        or "\n" in reason
        or "\r" in reason
    ):
        raise ValueError("Rejection reason must be a concise sanitized string.")

    return reason
