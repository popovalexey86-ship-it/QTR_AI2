from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from backtesting.simulated_broker import (
    SimulatedBroker,
    SimulatedOrderRejected,
)
from core.candle import Candle
from core.decision import Decision
from core.pending_entry import (
    PendingEntryStatus,
    build_order_link_id,
    build_setup_key,
)
from core.setup import Setup
from core.trade_request import TradeRequest
from core.trend import Trend


START = datetime(2025, 1, 1, tzinfo=UTC)


def candle(
    minute: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float | None = None,
) -> Candle:
    return Candle(
        timestamp=START + timedelta(minutes=minute),
        open=open_price,
        high=high,
        low=low,
        close=open_price if close is None else close,
        volume=1.0,
    )


def request(
    decision: Decision,
    *,
    signal_timestamp: datetime = START,
    entry: float = 100.0,
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> TradeRequest:
    bullish = decision == Decision.BUY
    normalized_stop = (
        stop_loss if stop_loss is not None else (95.0 if bullish else 105.0)
    )
    normalized_take_profit = (
        take_profit
        if take_profit is not None
        else (110.0 if bullish else 90.0)
    )
    setup = Setup(
        index=0,
        timestamp=signal_timestamp,
        trend=Trend.BULLISH if bullish else Trend.BEARISH,
        entry=entry,
        stop_loss=normalized_stop,
    )
    return TradeRequest(
        symbol="BTCUSDT",
        decision=decision,
        entry=entry,
        stop_loss=normalized_stop,
        take_profit=normalized_take_profit,
        volume=0.01,
        setup=setup,
    )


def submit(
    broker: SimulatedBroker,
    trade_request: TradeRequest,
    *,
    signal_timestamp: datetime = START,
) -> tuple[str, str]:
    setup_key = build_setup_key(
        symbol=trade_request.symbol,
        direction=trade_request.decision,
        setup_timestamp=signal_timestamp,
        entry=trade_request.entry,
        stop_loss=trade_request.stop_loss,
        take_profit=trade_request.take_profit,
    )
    order_link_id = build_order_link_id(setup_key)
    acknowledgement = broker.submit_entry(
        trade_request,
        order_link_id=order_link_id,
        setup_key=setup_key,
        signal_timestamp=signal_timestamp,
    )
    assert acknowledgement.exchange_order_id is not None
    return order_link_id, acknowledgement.exchange_order_id


@pytest.mark.parametrize("ttl", [0, -1, True, cast(int, 1.5)])
def test_pending_entry_ttl_requires_positive_non_bool_integer(ttl: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        SimulatedBroker("BTCUSDT", pending_entry_ttl_candles=ttl)


def test_submission_returns_stable_ack_without_immediate_position() -> None:
    broker = SimulatedBroker("BTCUSDT")
    order_link_id, exchange_order_id = submit(
        broker,
        request(Decision.BUY),
    )

    assert exchange_order_id == "SIM-ENTRY-000001"
    assert broker.get_open_position() is None
    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.status == PendingEntryStatus.SUBMITTED
    snapshot = broker.get_entry_order(order_link_id)
    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.SUBMITTED


def test_signal_candle_cannot_fill_or_age_pending_entry() -> None:
    broker = SimulatedBroker("BTCUSDT")
    order_link_id, _ = submit(broker, request(Decision.BUY))

    broker.update_market(
        candle(0, open_price=100.0, high=111.0, low=94.0)
    )

    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.status == PendingEntryStatus.SUBMITTED
    assert pending.completed_candles_active == 0
    assert broker.get_open_position() is None
    assert broker.get_entry_order(order_link_id) is not None


def test_duplicate_active_submission_is_idempotent_and_uses_one_entry_id() -> None:
    broker = SimulatedBroker("BTCUSDT")
    trade_request = request(Decision.BUY)
    order_link_id, first_exchange_id = submit(broker, trade_request)
    duplicate_link_id, duplicate_exchange_id = submit(broker, trade_request)

    assert duplicate_link_id == order_link_id
    assert duplicate_exchange_id == first_exchange_id

    broker.cancel_entry(order_link_id)
    second_request = request(
        Decision.BUY,
        signal_timestamp=START + timedelta(minutes=1),
        entry=99.0,
    )
    _, next_exchange_id = submit(
        broker,
        second_request,
        signal_timestamp=START + timedelta(minutes=1),
    )
    assert next_exchange_id == "SIM-ENTRY-000002"


def test_only_one_pending_entry_or_position_is_allowed() -> None:
    broker = SimulatedBroker("BTCUSDT")
    submit(broker, request(Decision.BUY))

    with pytest.raises(RuntimeError, match="already active"):
        submit(
            broker,
            request(
                Decision.SELL,
                signal_timestamp=START + timedelta(minutes=1),
            ),
            signal_timestamp=START + timedelta(minutes=1),
        )
    with pytest.raises(RuntimeError, match="entry is pending"):
        broker.open_position(request(Decision.BUY))


@pytest.mark.parametrize(
    ("decision", "eligible_candle"),
    [
        (
            Decision.BUY,
            candle(1, open_price=105.0, high=106.0, low=99.0),
        ),
        (
            Decision.SELL,
            candle(1, open_price=95.0, high=101.0, low=94.0),
        ),
    ],
)
def test_normal_next_candle_touch_fills_at_request_entry(
    decision: Decision,
    eligible_candle: Candle,
) -> None:
    broker = SimulatedBroker("BTCUSDT")
    order_link_id, _ = submit(broker, request(decision))

    broker.update_market(eligible_candle)

    position = broker.get_open_position()
    assert position is not None
    assert position.entry == 100.0
    assert position.opened_at == eligible_candle.timestamp
    assert position.ticket == "SIM-000001"
    assert broker.get_pending_entry() is None
    snapshot = broker.get_entry_order(order_link_id)
    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.FILLED
    assert snapshot.filled_volume == 0.01
    assert snapshot.average_fill_price == 100.0


@pytest.mark.parametrize(
    ("decision", "eligible_candle"),
    [
        (
            Decision.BUY,
            candle(1, open_price=105.0, high=106.0, low=100.0),
        ),
        (
            Decision.SELL,
            candle(1, open_price=95.0, high=100.0, low=94.0),
        ),
    ],
)
def test_exact_low_or_high_boundary_counts_as_touch(
    decision: Decision,
    eligible_candle: Candle,
) -> None:
    broker = SimulatedBroker("BTCUSDT")
    submit(broker, request(decision))

    broker.update_market(eligible_candle)

    assert broker.get_open_position() is not None


@pytest.mark.parametrize(
    ("decision", "eligible_candle"),
    [
        (
            Decision.BUY,
            candle(1, open_price=99.0, high=99.0, low=98.0),
        ),
        (
            Decision.SELL,
            candle(1, open_price=101.0, high=102.0, low=101.0),
        ),
    ],
)
def test_favourable_gap_fills_at_limit_not_candle_open(
    decision: Decision,
    eligible_candle: Candle,
) -> None:
    broker = SimulatedBroker("BTCUSDT")
    submit(broker, request(decision))

    broker.update_market(eligible_candle)

    position = broker.get_open_position()
    assert position is not None
    assert position.entry == 100.0
    assert position.entry != eligible_candle.open


@pytest.mark.parametrize(
    ("decision", "eligible_candle"),
    [
        (
            Decision.BUY,
            candle(1, open_price=102.0, high=103.0, low=101.0),
        ),
        (
            Decision.SELL,
            candle(1, open_price=98.0, high=99.0, low=97.0),
        ),
    ],
)
def test_gap_away_remains_pending(
    decision: Decision,
    eligible_candle: Candle,
) -> None:
    broker = SimulatedBroker("BTCUSDT")
    submit(broker, request(decision))

    broker.update_market(eligible_candle)

    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.status == PendingEntryStatus.WORKING
    assert pending.completed_candles_active == 1
    assert broker.get_open_position() is None


@pytest.mark.parametrize(
    (
        "decision",
        "marketable_at_open",
        "high",
        "low",
        "expected_exit",
    ),
    [
        (Decision.BUY, 99.0, 105.0, 94.0, 95.0),
        (Decision.BUY, 99.0, 111.0, 98.0, 110.0),
        (Decision.BUY, 99.0, 111.0, 94.0, 95.0),
        (Decision.SELL, 101.0, 106.0, 95.0, 105.0),
        (Decision.SELL, 101.0, 102.0, 89.0, 90.0),
        (Decision.SELL, 101.0, 106.0, 89.0, 105.0),
    ],
)
def test_marketable_at_open_evaluates_same_candle_stop_first(
    decision: Decision,
    marketable_at_open: float,
    high: float,
    low: float,
    expected_exit: float,
) -> None:
    broker = SimulatedBroker("BTCUSDT")
    order_link_id, _ = submit(broker, request(decision))

    broker.update_market(
        candle(
            1,
            open_price=marketable_at_open,
            high=high,
            low=low,
        )
    )

    assert broker.get_open_position() is None
    trade = broker.get_last_closed_trade()
    assert trade is not None
    assert trade.exit == expected_exit
    assert trade.entry == 100.0
    snapshot = broker.get_entry_order(order_link_id)
    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.FILLED


@pytest.mark.parametrize(
    ("decision", "open_price", "high", "low", "expected_exit"),
    [
        (Decision.BUY, 105.0, 106.0, 94.0, 95.0),
        (Decision.BUY, 105.0, 111.0, 99.0, None),
        (Decision.BUY, 105.0, 111.0, 94.0, 95.0),
        (Decision.SELL, 95.0, 106.0, 94.0, 105.0),
        (Decision.SELL, 95.0, 101.0, 89.0, None),
        (Decision.SELL, 95.0, 106.0, 89.0, 105.0),
    ],
)
def test_intrabar_fill_allows_stop_but_does_not_credit_tp_only(
    decision: Decision,
    open_price: float,
    high: float,
    low: float,
    expected_exit: float | None,
) -> None:
    broker = SimulatedBroker("BTCUSDT")
    submit(broker, request(decision))

    broker.update_market(
        candle(1, open_price=open_price, high=high, low=low)
    )

    trade = broker.get_last_closed_trade()
    if expected_exit is None:
        assert trade is None
        assert broker.get_open_position() is not None
    else:
        assert trade is not None
        assert trade.exit == expected_exit
        assert broker.get_open_position() is None


@pytest.mark.parametrize(
    ("decision", "next_candle"),
    [
        (
            Decision.BUY,
            candle(2, open_price=105.0, high=111.0, low=100.0),
        ),
        (
            Decision.SELL,
            candle(2, open_price=95.0, high=100.0, low=89.0),
        ),
    ],
)
def test_intrabar_tp_becomes_eligible_on_next_candle(
    decision: Decision,
    next_candle: Candle,
) -> None:
    broker = SimulatedBroker("BTCUSDT")
    submit(broker, request(decision))
    first_candle = (
        candle(1, open_price=105.0, high=111.0, low=99.0)
        if decision == Decision.BUY
        else candle(1, open_price=95.0, high=101.0, low=89.0)
    )
    broker.update_market(first_candle)
    assert broker.get_open_position() is not None
    broker.update_market(first_candle)
    assert broker.get_open_position() is not None

    broker.update_market(next_candle)

    trade = broker.get_last_closed_trade()
    assert trade is not None
    assert trade.exit == (110.0 if decision == Decision.BUY else 90.0)


def test_signal_and_first_three_active_candles_do_not_expire_order() -> None:
    broker = SimulatedBroker("BTCUSDT", pending_entry_ttl_candles=4)
    submit(broker, request(Decision.BUY))

    broker.update_market(
        candle(0, open_price=102.0, high=103.0, low=101.0)
    )
    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.completed_candles_active == 0

    for active_candle in range(1, 4):
        broker.update_market(
            candle(
                active_candle,
                open_price=102.0,
                high=103.0,
                low=101.0,
            )
        )
        pending = broker.get_pending_entry()
        assert pending is not None
        assert pending.status == PendingEntryStatus.WORKING
        assert pending.completed_candles_active == active_candle


def test_fourth_active_candle_remains_fillable_before_expiry() -> None:
    broker = SimulatedBroker("BTCUSDT", pending_entry_ttl_candles=4)
    order_link_id, _ = submit(broker, request(Decision.BUY))
    for active_candle in range(1, 4):
        broker.update_market(
            candle(
                active_candle,
                open_price=102.0,
                high=103.0,
                low=101.0,
            )
        )

    broker.update_market(
        candle(4, open_price=102.0, high=103.0, low=100.0)
    )

    assert broker.get_open_position() is not None
    snapshot = broker.get_entry_order(order_link_id)
    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.FILLED


def test_unfilled_order_expires_after_fourth_candle_and_remains_queryable() -> None:
    broker = SimulatedBroker("BTCUSDT", pending_entry_ttl_candles=4)
    order_link_id, _ = submit(broker, request(Decision.BUY))

    for active_candle in range(1, 5):
        broker.update_market(
            candle(
                active_candle,
                open_price=102.0,
                high=103.0,
                low=101.0,
            )
        )

    assert broker.get_pending_entry() is None
    assert broker.get_open_position() is None
    snapshot = broker.get_entry_order(order_link_id)
    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.EXPIRED


def test_manual_cancellation_is_idempotent_and_snapshot_remains_queryable() -> None:
    broker = SimulatedBroker("BTCUSDT")
    order_link_id, _ = submit(broker, request(Decision.BUY))

    broker.cancel_entry(order_link_id)
    broker.cancel_entry(order_link_id)
    broker.cancel_entry("missing-order")

    assert broker.get_pending_entry() is None
    snapshot = broker.get_entry_order(order_link_id)
    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.CANCELLED


def test_working_order_cancellation_is_terminal() -> None:
    broker = SimulatedBroker("BTCUSDT")
    order_link_id, _ = submit(broker, request(Decision.BUY))
    broker.update_market(
        candle(1, open_price=102.0, high=103.0, low=101.0)
    )

    broker.cancel_entry(order_link_id)

    snapshot = broker.get_entry_order(order_link_id)
    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.CANCELLED
    assert broker.get_pending_entry() is None


def test_entry_and_position_ticket_counters_are_independent() -> None:
    broker = SimulatedBroker("BTCUSDT")
    first_link_id, first_entry_id = submit(broker, request(Decision.BUY))
    broker.cancel_entry(first_link_id)
    broker.update_market(
        candle(0, open_price=100.0, high=100.0, low=100.0)
    )

    position = broker.open_position(request(Decision.BUY))
    assert first_entry_id == "SIM-ENTRY-000001"
    assert position.ticket == "SIM-000001"
    broker.close_position(position)

    second_signal = START + timedelta(minutes=1)
    _, second_entry_id = submit(
        broker,
        request(Decision.BUY, signal_timestamp=second_signal, entry=99.0),
        signal_timestamp=second_signal,
    )
    assert second_entry_id == "SIM-ENTRY-000002"


def test_open_position_blocks_pending_submission() -> None:
    broker = SimulatedBroker("BTCUSDT")
    broker.update_market(
        candle(0, open_price=100.0, high=100.0, low=100.0)
    )
    broker.open_position(request(Decision.BUY))

    with pytest.raises(RuntimeError, match="position is open"):
        submit(broker, request(Decision.BUY))


def test_rejected_pending_snapshot_remains_queryable_without_position() -> None:
    broker = SimulatedBroker("BTCUSDT")
    invalid_request = request(Decision.BUY, stop_loss=101.0)
    setup_key = build_setup_key(
        symbol=invalid_request.symbol,
        direction=invalid_request.decision,
        setup_timestamp=START,
        entry=invalid_request.entry,
        stop_loss=invalid_request.stop_loss,
        take_profit=invalid_request.take_profit,
    )
    order_link_id = build_order_link_id(setup_key)

    with pytest.raises(SimulatedOrderRejected):
        broker.submit_entry(
            invalid_request,
            order_link_id=order_link_id,
            setup_key=setup_key,
            signal_timestamp=START,
        )

    assert broker.get_pending_entry() is None
    assert broker.get_open_position() is None
    snapshot = broker.get_entry_order(order_link_id)
    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.REJECTED
