from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
import math
import re

import pytest

from core.decision import Decision
from core.entry_order import EntryOrderAcknowledgement, EntryOrderSnapshot
from core.pending_entry import (
    InvalidPendingEntryTransition,
    PendingEntry,
    PendingEntryStatus,
    build_order_link_id,
    build_setup_key,
    validate_pending_entry_transition,
)
from core.setup import Setup
from core.trade_request import TradeRequest
from core.trend import Trend


SIGNAL_TIME = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)


def make_request(volume: float = 1.0) -> TradeRequest:
    setup = Setup(
        index=10,
        timestamp=SIGNAL_TIME,
        trend=Trend.BULLISH,
        entry=100.0,
        stop_loss=95.0,
    )
    return TradeRequest(
        symbol="BTCUSDT",
        decision=Decision.BUY,
        entry=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        volume=volume,
        setup=setup,
    )


def make_pending_entry(
    *,
    status: PendingEntryStatus = PendingEntryStatus.SUBMITTED,
    filled_volume: float = 0.0,
    average_fill_price: float | None = None,
    signal_timestamp: datetime = SIGNAL_TIME,
    completed_candles_active: int = 0,
    request: TradeRequest | None = None,
) -> PendingEntry:
    return PendingEntry(
        order_link_id="QTR-0123456789abcdef",
        setup_key="qtr-setup-v1:0123456789abcdef",
        request=request or make_request(),
        signal_timestamp=signal_timestamp,
        status=status,
        exchange_order_id="exchange-1",
        completed_candles_active=completed_candles_active,
        filled_volume=filled_volume,
        average_fill_price=average_fill_price,
    )


ALLOWED_TRANSITIONS = {
    PendingEntryStatus.SUBMITTED: {
        PendingEntryStatus.WORKING,
        PendingEntryStatus.PARTIALLY_FILLED,
        PendingEntryStatus.CANCEL_REQUESTED,
        PendingEntryStatus.FILLED,
        PendingEntryStatus.CANCELLED,
        PendingEntryStatus.REJECTED,
    },
    PendingEntryStatus.WORKING: {
        PendingEntryStatus.PARTIALLY_FILLED,
        PendingEntryStatus.FILLED,
        PendingEntryStatus.CANCEL_REQUESTED,
        PendingEntryStatus.CANCELLED,
        PendingEntryStatus.REJECTED,
    },
    PendingEntryStatus.PARTIALLY_FILLED: {
        PendingEntryStatus.PARTIALLY_FILLED,
        PendingEntryStatus.FILLED,
        PendingEntryStatus.CANCEL_REQUESTED,
        PendingEntryStatus.CANCELLED,
        PendingEntryStatus.REJECTED,
    },
    PendingEntryStatus.CANCEL_REQUESTED: {
        PendingEntryStatus.FILLED,
        PendingEntryStatus.PARTIALLY_FILLED,
        PendingEntryStatus.CANCELLED,
        PendingEntryStatus.REJECTED,
        PendingEntryStatus.EXPIRED,
    },
}


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (current, target)
        for current, targets in ALLOWED_TRANSITIONS.items()
        for target in targets
    ],
)
def test_all_approved_status_transitions_are_allowed(
    current: PendingEntryStatus,
    target: PendingEntryStatus,
) -> None:
    validate_pending_entry_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (PendingEntryStatus.WORKING, PendingEntryStatus.SUBMITTED),
        (PendingEntryStatus.CANCEL_REQUESTED, PendingEntryStatus.WORKING),
        (PendingEntryStatus.SUBMITTED, PendingEntryStatus.EXPIRED),
    ],
)
def test_forbidden_status_transitions_raise_domain_error(
    current: PendingEntryStatus,
    target: PendingEntryStatus,
) -> None:
    with pytest.raises(InvalidPendingEntryTransition):
        validate_pending_entry_transition(current, target)


def test_expired_requires_confirmed_ttl_cancellation_transition() -> None:
    validate_pending_entry_transition(
        PendingEntryStatus.CANCEL_REQUESTED,
        PendingEntryStatus.EXPIRED,
    )

    for current in (
        PendingEntryStatus.WORKING,
        PendingEntryStatus.PARTIALLY_FILLED,
    ):
        with pytest.raises(InvalidPendingEntryTransition):
            validate_pending_entry_transition(
                current,
                PendingEntryStatus.EXPIRED,
            )


def test_submitted_can_request_asynchronous_live_cancellation() -> None:
    validate_pending_entry_transition(
        PendingEntryStatus.SUBMITTED,
        PendingEntryStatus.CANCEL_REQUESTED,
    )

    with pytest.raises(InvalidPendingEntryTransition):
        validate_pending_entry_transition(
            PendingEntryStatus.SUBMITTED,
            PendingEntryStatus.EXPIRED,
        )


@pytest.mark.parametrize(
    "terminal",
    [
        PendingEntryStatus.FILLED,
        PendingEntryStatus.CANCELLED,
        PendingEntryStatus.REJECTED,
        PendingEntryStatus.EXPIRED,
    ],
)
def test_terminal_statuses_have_no_outgoing_transitions(
    terminal: PendingEntryStatus,
) -> None:
    for target in PendingEntryStatus:
        with pytest.raises(InvalidPendingEntryTransition):
            validate_pending_entry_transition(terminal, target)


def test_setup_key_is_stable_and_normalizes_same_utc_instant() -> None:
    first = build_setup_key(
        symbol="btcusdt",
        direction=Decision.BUY,
        setup_timestamp=SIGNAL_TIME,
        entry=100.0,
        stop_loss=95.0,
        take_profit=110.0,
    )
    equivalent_time = SIGNAL_TIME.astimezone(timezone(timedelta(hours=3)))
    second = build_setup_key(
        symbol="btcusdt",
        direction=Decision.BUY,
        setup_timestamp=equivalent_time,
        entry=100.0,
        stop_loss=95.0,
        take_profit=110.0,
    )

    assert first == second
    assert first == (
        "qtr-setup-v1:"
        "8c7e6ef610e8d8dd7f1c24def60893ca5f955dc472baab020c36871cc5aab5e7"
    )
    assert first != build_setup_key(
        symbol="btcusdt",
        direction=Decision.BUY,
        setup_timestamp=SIGNAL_TIME,
        entry=101.0,
        stop_loss=95.0,
        take_profit=110.0,
    )


def test_order_link_id_is_stable_ascii_safe_and_bybit_sized() -> None:
    setup_key = build_setup_key(
        symbol="BTCUSDT",
        direction=Decision.BUY,
        setup_timestamp=SIGNAL_TIME,
        entry=100.0,
        stop_loss=95.0,
        take_profit=110.0,
    )

    first = build_order_link_id(setup_key)
    second = build_order_link_id(setup_key)

    assert first == second
    assert first.startswith("QTR-")
    assert len(first) == 36
    assert first == "QTR-366dc7d2f23191414ba49baa65db8f4c"
    assert re.fullmatch(r"[A-Za-z0-9_-]+", first)
    first.encode("ascii")


def test_pending_entry_requires_timezone_aware_signal_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        make_pending_entry(signal_timestamp=datetime(2025, 1, 1, 12, 0))


def test_pending_entry_requires_non_empty_order_link_id() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        PendingEntry(
            order_link_id=" ",
            setup_key="setup-key",
            request=make_request(),
            signal_timestamp=SIGNAL_TIME,
        )


def test_pending_entry_requires_non_empty_setup_key() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        PendingEntry(
            order_link_id="QTR-order",
            setup_key=" ",
            request=make_request(),
            signal_timestamp=SIGNAL_TIME,
        )


def test_setup_identity_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        build_setup_key(
            symbol="BTCUSDT",
            direction=Decision.BUY,
            setup_timestamp=datetime(2025, 1, 1, 12, 0),
            entry=100.0,
            stop_loss=95.0,
            take_profit=110.0,
        )


@pytest.mark.parametrize("value", [-1, -100])
def test_pending_entry_rejects_negative_active_candle_count(value: int) -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        make_pending_entry(completed_candles_active=value)


@pytest.mark.parametrize("filled_volume", [-1.0, math.inf, math.nan])
def test_pending_entry_rejects_invalid_filled_volume(
    filled_volume: float,
) -> None:
    with pytest.raises(ValueError, match="finite and non-negative"):
        make_pending_entry(filled_volume=filled_volume)


def test_pending_entry_rejects_volume_above_request() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        make_pending_entry(
            status=PendingEntryStatus.FILLED,
            filled_volume=1.1,
            average_fill_price=100.0,
        )


def test_pending_entry_rejects_non_finite_requested_volume() -> None:
    request = make_request(volume=math.inf)

    with pytest.raises(ValueError, match="finite and positive"):
        make_pending_entry(request=request)


@pytest.mark.parametrize("average_price", [0.0, -1.0, math.inf, math.nan])
def test_pending_entry_rejects_invalid_average_fill_price(
    average_price: float,
) -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        make_pending_entry(
            status=PendingEntryStatus.PARTIALLY_FILLED,
            filled_volume=0.5,
            average_fill_price=average_price,
        )


def test_partial_fill_requires_partial_volume_and_average_price() -> None:
    entry = make_pending_entry(
        status=PendingEntryStatus.PARTIALLY_FILLED,
        filled_volume=0.4,
        average_fill_price=99.5,
    )

    assert entry.filled_volume == 0.4
    assert entry.average_fill_price == 99.5

    with pytest.raises(ValueError, match="between zero"):
        make_pending_entry(status=PendingEntryStatus.PARTIALLY_FILLED)

    with pytest.raises(ValueError, match="requires an average"):
        make_pending_entry(
            status=PendingEntryStatus.PARTIALLY_FILLED,
            filled_volume=0.4,
        )


def test_full_fill_requires_entire_volume_and_average_price() -> None:
    entry = make_pending_entry(
        status=PendingEntryStatus.FILLED,
        filled_volume=1.0,
        average_fill_price=100.0,
    )

    assert entry.filled_volume == entry.request.volume

    with pytest.raises(ValueError, match="entire requested volume"):
        make_pending_entry(
            status=PendingEntryStatus.FILLED,
            filled_volume=0.5,
            average_fill_price=100.0,
        )


def test_non_filled_terminal_state_may_retain_partial_fill() -> None:
    entry = make_pending_entry(
        status=PendingEntryStatus.CANCELLED,
        filled_volume=0.4,
        average_fill_price=99.5,
    )

    assert entry.status == PendingEntryStatus.CANCELLED
    assert entry.filled_volume == 0.4


def test_pending_entry_is_immutable() -> None:
    entry = make_pending_entry()

    with pytest.raises(FrozenInstanceError):
        setattr(entry, "status", PendingEntryStatus.WORKING)


def test_entry_order_domain_types_are_immutable_and_normalized() -> None:
    acknowledgement = EntryOrderAcknowledgement(
        order_link_id="QTR-order",
        exchange_order_id="exchange-order",
    )
    snapshot = EntryOrderSnapshot(
        order_link_id=acknowledgement.order_link_id,
        exchange_order_id=acknowledgement.exchange_order_id,
        status=PendingEntryStatus.PARTIALLY_FILLED,
        requested_volume=1.0,
        filled_volume=0.25,
        average_fill_price=100.0,
    )

    assert snapshot.filled_volume == 0.25
    assert not hasattr(snapshot, "raw_payload")
    with pytest.raises(FrozenInstanceError):
        setattr(snapshot, "status", PendingEntryStatus.FILLED)


def test_sanitized_rejection_reason_is_not_exposed_in_repr() -> None:
    reason = "insufficient margin"
    snapshot = EntryOrderSnapshot(
        order_link_id="QTR-order",
        exchange_order_id="exchange-order",
        status=PendingEntryStatus.REJECTED,
        requested_volume=1.0,
        filled_volume=0.0,
        rejection_reason=reason,
    )

    assert snapshot.rejection_reason == reason
    assert reason not in repr(snapshot)


def test_rejection_reason_is_safely_normalized() -> None:
    snapshot = EntryOrderSnapshot(
        order_link_id="QTR-order",
        exchange_order_id="exchange-order",
        status=PendingEntryStatus.REJECTED,
        requested_volume=1.0,
        filled_volume=0.0,
        rejection_reason="  insufficient margin  ",
    )

    assert snapshot.rejection_reason == "insufficient margin"
    assert "insufficient margin" not in repr(snapshot)


def test_raw_rejection_data_is_rejected_without_echoing_it() -> None:
    raw_reason = "token=super-secret\nraw={'retCode': 10001}"

    with pytest.raises(ValueError) as error:
        EntryOrderSnapshot(
            order_link_id="QTR-order",
            exchange_order_id="exchange-order",
            status=PendingEntryStatus.REJECTED,
            requested_volume=1.0,
            filled_volume=0.0,
            rejection_reason=raw_reason,
        )

    assert "super-secret" not in str(error.value)
    assert "retCode" not in str(error.value)


def test_domain_validation_errors_do_not_echo_identifier_values() -> None:
    secret_like_value = "api-token-super-secret"

    with pytest.raises(ValueError) as error:
        EntryOrderAcknowledgement(
            order_link_id=" ",
            exchange_order_id=secret_like_value,
        )

    assert secret_like_value not in str(error.value)
