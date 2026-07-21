import math

import pytest

from core.pending_entry import PendingEntryStatus
from infrastructure.bybit.bybit_entry_order_snapshot_mapper import (
    BybitEntryOrderSnapshotError,
    BybitEntryOrderSnapshotMapper,
    extract_order_items,
    select_order_item,
)


ORDER_LINK_ID = "QTR-0123456789abcdef"


def item(
    status: str,
    *,
    qty: object = "1",
    filled: object = "0",
    average: object = "",
    reason: object = "EC_NoError",
    order_link_id: str = ORDER_LINK_ID,
) -> dict[str, object]:
    return {
        "orderLinkId": order_link_id,
        "orderId": "exchange-order-1",
        "orderStatus": status,
        "qty": qty,
        "cumExecQty": filled,
        "avgPrice": average,
        "rejectReason": reason,
        "rawSecret": "must-not-be-retained",
    }


@pytest.mark.parametrize(
    ("raw_status", "status", "filled", "average"),
    [
        ("Created", PendingEntryStatus.SUBMITTED, "0", ""),
        ("New", PendingEntryStatus.WORKING, "0", "0"),
        ("PartiallyFilled", PendingEntryStatus.PARTIALLY_FILLED, "0.4", "100"),
        ("PendingCancel", PendingEntryStatus.CANCEL_REQUESTED, "0", ""),
        ("Filled", PendingEntryStatus.FILLED, "1", "100"),
        ("Cancelled", PendingEntryStatus.CANCELLED, "0", ""),
        ("Rejected", PendingEntryStatus.REJECTED, "0", ""),
    ],
)
def test_maps_every_supported_status(
    raw_status: str,
    status: PendingEntryStatus,
    filled: str,
    average: str,
) -> None:
    snapshot = BybitEntryOrderSnapshotMapper.from_item(
        item(raw_status, filled=filled, average=average),
        expected_order_link_id=ORDER_LINK_ID,
    )

    assert snapshot.status == status
    assert snapshot.filled_volume == float(filled)
    assert snapshot.average_fill_price == (
        None if average in ("", "0") else float(average)
    )
    assert not hasattr(snapshot, "rawSecret")


def test_cancelled_order_may_retain_a_partial_fill() -> None:
    snapshot = BybitEntryOrderSnapshotMapper.from_item(
        item("Cancelled", filled="0.4", average="99.5"),
        expected_order_link_id=ORDER_LINK_ID,
    )

    assert snapshot.status == PendingEntryStatus.CANCELLED
    assert snapshot.filled_volume == 0.4
    assert snapshot.average_fill_price == 99.5


def test_rejection_reason_is_sanitized_and_hidden_from_repr() -> None:
    snapshot = BybitEntryOrderSnapshotMapper.from_item(
        item("Rejected", reason="  EC_BadRequest\ninternal detail  "),
        expected_order_link_id=ORDER_LINK_ID,
    )

    assert snapshot.rejection_reason == "EC_BadRequest internal detail"
    assert snapshot.rejection_reason not in repr(snapshot)


def test_ec_no_error_is_not_retained_as_rejection_reason() -> None:
    snapshot = BybitEntryOrderSnapshotMapper.from_item(
        item("Rejected", reason=" EC_NoError "),
        expected_order_link_id=ORDER_LINK_ID,
    )

    assert snapshot.rejection_reason is None


def test_rejection_reason_is_discarded_for_non_rejected_status() -> None:
    snapshot = BybitEntryOrderSnapshotMapper.from_item(
        item("New", reason="sensitive internal detail"),
        expected_order_link_id=ORDER_LINK_ID,
    )

    assert snapshot.rejection_reason is None


@pytest.mark.parametrize("average", ["", "0", 0])
def test_empty_or_zero_average_price_is_none_without_fill(average: object) -> None:
    snapshot = BybitEntryOrderSnapshotMapper.from_item(
        item("Cancelled", average=average),
        expected_order_link_id=ORDER_LINK_ID,
    )

    assert snapshot.average_fill_price is None


@pytest.mark.parametrize(
    ("field_name", "value", "status", "filled", "average"),
    [
        ("qty", "bad", "New", "0", ""),
        ("qty", math.inf, "New", "0", ""),
        ("filled", "bad", "PartiallyFilled", "0.4", "100"),
        ("filled", math.nan, "PartiallyFilled", "0.4", "100"),
        ("average", "bad", "PartiallyFilled", "0.4", "100"),
        ("average", "", "PartiallyFilled", "0.4", ""),
    ],
)
def test_malformed_numeric_fields_fail_with_safe_broker_error(
    field_name: str,
    value: object,
    status: str,
    filled: object,
    average: object,
) -> None:
    values = {"qty": "1", "filled": filled, "average": average}
    values[field_name] = value

    with pytest.raises(BybitEntryOrderSnapshotError, match="Bybit order"):
        BybitEntryOrderSnapshotMapper.from_item(
            item(
                status,
                qty=values["qty"],
                filled=values["filled"],
                average=values["average"],
            ),
            expected_order_link_id=ORDER_LINK_ID,
        )


def test_mismatched_order_link_id_fails_closed() -> None:
    with pytest.raises(BybitEntryOrderSnapshotError, match="does not match"):
        BybitEntryOrderSnapshotMapper.from_item(
            item("New", order_link_id="QTR-other"),
            expected_order_link_id=ORDER_LINK_ID,
        )


def test_unknown_status_fails_closed() -> None:
    with pytest.raises(BybitEntryOrderSnapshotError, match="unsupported"):
        BybitEntryOrderSnapshotMapper.from_item(
            item("Deactivated"),
            expected_order_link_id=ORDER_LINK_ID,
        )


def response(*items: dict[str, object], ret_code: int = 0) -> dict[str, object]:
    return {"retCode": ret_code, "result": {"list": list(items)}}


def test_response_helpers_extract_and_select_exact_match() -> None:
    other = item("New", order_link_id="QTR-other")
    expected = item("New")
    payload = response(other, expected)

    assert extract_order_items(payload) == (other, expected)
    assert select_order_item(
        payload,
        expected_order_link_id=ORDER_LINK_ID,
    ) is expected
    snapshot = BybitEntryOrderSnapshotMapper.from_response(
        payload,
        expected_order_link_id=ORDER_LINK_ID,
    )
    assert snapshot is not None
    assert snapshot.order_link_id == ORDER_LINK_ID


def test_response_helper_distinguishes_no_match() -> None:
    payload = response(item("New", order_link_id="QTR-other"))

    assert select_order_item(
        payload,
        expected_order_link_id=ORDER_LINK_ID,
    ) is None
    assert BybitEntryOrderSnapshotMapper.from_response(
        payload,
        expected_order_link_id=ORDER_LINK_ID,
    ) is None


def test_response_helper_rejects_multiple_matches() -> None:
    with pytest.raises(BybitEntryOrderSnapshotError, match="multiple"):
        select_order_item(
            response(item("New"), item("New")),
            expected_order_link_id=ORDER_LINK_ID,
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"retCode": 10001, "retMsg": "sensitive-environment-secret"},
        {"retCode": 0},
        {"retCode": 0, "result": {}},
        {"retCode": 0, "result": {"list": ["bad-item"]}},
    ],
)
def test_response_helper_rejects_malformed_or_failed_response_safely(
    payload: dict[str, object],
) -> None:
    with pytest.raises(BybitEntryOrderSnapshotError) as error:
        extract_order_items(payload)

    assert "sensitive-environment-secret" not in str(error.value)
