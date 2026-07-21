from collections.abc import Mapping
import math
from typing import Any

from core.entry_order import EntryOrderSnapshot
from core.exceptions import BrokerError
from core.pending_entry import PendingEntryStatus


class BybitEntryOrderSnapshotError(BrokerError):
    """Raised when a Bybit order response cannot be mapped safely."""


_STATUS_MAPPING = {
    "Created": PendingEntryStatus.SUBMITTED,
    "New": PendingEntryStatus.WORKING,
    "PartiallyFilled": PendingEntryStatus.PARTIALLY_FILLED,
    "PendingCancel": PendingEntryStatus.CANCEL_REQUESTED,
    "Filled": PendingEntryStatus.FILLED,
    "Cancelled": PendingEntryStatus.CANCELLED,
    "Rejected": PendingEntryStatus.REJECTED,
}


class BybitEntryOrderSnapshotMapper:
    @staticmethod
    def from_response(
        response: Mapping[str, Any],
        *,
        expected_order_link_id: str,
    ) -> EntryOrderSnapshot | None:
        item = select_order_item(
            response,
            expected_order_link_id=expected_order_link_id,
        )
        if item is None:
            return None
        return BybitEntryOrderSnapshotMapper.from_item(
            item,
            expected_order_link_id=expected_order_link_id,
        )

    @staticmethod
    def from_item(
        item: Mapping[str, Any],
        *,
        expected_order_link_id: str,
    ) -> EntryOrderSnapshot:
        order_link_id = _required_string(item, "orderLinkId")
        if order_link_id != expected_order_link_id:
            raise BybitEntryOrderSnapshotError(
                "Bybit order link ID does not match the requested order."
            )

        order_id = _required_string(item, "orderId")
        raw_status = _required_string(item, "orderStatus")
        try:
            status = _STATUS_MAPPING[raw_status]
        except KeyError:
            raise BybitEntryOrderSnapshotError(
                "Bybit returned an unsupported order status."
            ) from None

        requested_volume = _parse_number(item.get("qty"), field_name="quantity")
        filled_volume = _parse_number(
            item.get("cumExecQty"),
            field_name="filled quantity",
        )
        average_fill_price = _parse_average_fill_price(
            item.get("avgPrice"),
            filled_volume=filled_volume,
        )
        rejection_reason = _map_rejection_reason(
            status,
            item.get("rejectReason"),
        )

        try:
            return EntryOrderSnapshot(
                order_link_id=order_link_id,
                exchange_order_id=order_id,
                status=status,
                requested_volume=requested_volume,
                filled_volume=filled_volume,
                average_fill_price=average_fill_price,
                rejection_reason=rejection_reason,
            )
        except ValueError:
            raise BybitEntryOrderSnapshotError(
                "Bybit order fill fields violate the domain contract."
            ) from None


def extract_order_items(
    response: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    ret_code = response.get("retCode")
    if (
        isinstance(ret_code, bool)
        or not isinstance(ret_code, int)
        or ret_code != 0
    ):
        raise BybitEntryOrderSnapshotError(
            "Bybit order query returned an unsuccessful response."
        )

    result = response.get("result")
    if not isinstance(result, Mapping):
        raise BybitEntryOrderSnapshotError(
            "Bybit order query result is malformed."
        )
    items = result.get("list")
    if not isinstance(items, list):
        raise BybitEntryOrderSnapshotError(
            "Bybit order query list is malformed."
        )
    if any(not isinstance(item, Mapping) for item in items):
        raise BybitEntryOrderSnapshotError(
            "Bybit order query contains a malformed item."
        )
    return tuple(items)


def select_order_item(
    response: Mapping[str, Any],
    *,
    expected_order_link_id: str,
) -> Mapping[str, Any] | None:
    matches = tuple(
        item
        for item in extract_order_items(response)
        if item.get("orderLinkId") == expected_order_link_id
    )
    if not matches:
        return None
    if len(matches) > 1:
        raise BybitEntryOrderSnapshotError(
            "Bybit returned multiple matching entry orders."
        )
    return matches[0]


def _required_string(item: Mapping[str, Any], field_name: str) -> str:
    value = item.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise BybitEntryOrderSnapshotError(
            "Bybit order contains a missing or malformed identifier."
        )
    return value.strip()


def _parse_number(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise BybitEntryOrderSnapshotError(
            f"Bybit order {field_name} is malformed."
        )
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise BybitEntryOrderSnapshotError(
            f"Bybit order {field_name} is malformed."
        ) from None
    if not math.isfinite(number):
        raise BybitEntryOrderSnapshotError(
            f"Bybit order {field_name} is malformed."
        )
    return number


def _parse_average_fill_price(
    value: object,
    *,
    filled_volume: float,
) -> float | None:
    if value is None or value == "":
        if filled_volume == 0:
            return None
        raise BybitEntryOrderSnapshotError(
            "Bybit order average fill price is missing for a fill."
        )

    average_fill_price = _parse_number(
        value,
        field_name="average fill price",
    )
    if average_fill_price == 0 and filled_volume == 0:
        return None
    if average_fill_price <= 0:
        raise BybitEntryOrderSnapshotError(
            "Bybit order average fill price must be positive for a fill."
        )
    return average_fill_price


def _map_rejection_reason(
    status: PendingEntryStatus,
    value: object,
) -> str | None:
    if status != PendingEntryStatus.REJECTED:
        return None
    if not isinstance(value, str):
        return None

    sanitized = " ".join(
        "".join(character if character.isprintable() else " " for character in value)
        .split()
    )
    if not sanitized or sanitized == "EC_NoError":
        return None
    return sanitized[:200]
