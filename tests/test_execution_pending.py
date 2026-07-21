from datetime import UTC, datetime, timedelta

import pytest

from backtesting.simulated_broker import SimulatedBroker, SimulatedOrderRejected
from core.decision import Decision
from core.exceptions import (
    DuplicatePendingSetupError,
    PendingEntryConflictError,
)
from core.execution import Execution
from core.pending_entry import (
    PendingEntryStatus,
    build_order_link_id,
    build_setup_key,
)
from core.setup import Setup
from core.trade_request import TradeRequest
from core.trend import Trend
from tests.test_simulated_pending_entry import candle


START = datetime(2025, 1, 1, tzinfo=UTC)


def request(
    *,
    setup_timestamp: datetime = START - timedelta(days=30),
    entry: float = 100.0,
    stop_loss: float = 95.0,
) -> TradeRequest:
    setup = Setup(
        index=1,
        timestamp=setup_timestamp,
        trend=Trend.BULLISH,
        entry=entry,
        stop_loss=stop_loss,
    )
    return TradeRequest(
        symbol="BTCUSDT",
        decision=Decision.BUY,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=entry + abs(entry - stop_loss) * 2,
        volume=0.01,
        setup=setup,
    )


def submit(
    execution: Execution,
    trade_request: TradeRequest,
    *,
    signal_timestamp: datetime = START,
    authoritative_symbol: str = "BTCUSDT",
):
    return execution.submit_pending_entry(
        trade_request,
        setup_timestamp=trade_request.setup.timestamp,
        signal_timestamp=signal_timestamp,
        authoritative_symbol=authoritative_symbol,
    )


def test_execution_builds_identity_from_authoritative_symbol_and_setup_time() -> None:
    broker = SimulatedBroker("ETHUSDT")
    execution = Execution(broker)
    trade_request = request()

    pending = submit(
        execution,
        trade_request,
        signal_timestamp=START,
        authoritative_symbol="ETHUSDT",
    )

    expected_key = build_setup_key(
        symbol="ETHUSDT",
        direction=trade_request.decision,
        setup_timestamp=trade_request.setup.timestamp,
        entry=trade_request.entry,
        stop_loss=trade_request.stop_loss,
        take_profit=trade_request.take_profit,
    )
    assert pending.setup_key == expected_key
    assert pending.order_link_id == build_order_link_id(expected_key)
    assert pending.signal_timestamp == START
    assert pending.signal_timestamp != trade_request.setup.timestamp


def test_active_pending_entry_blocks_another_submission() -> None:
    execution = Execution(SimulatedBroker("BTCUSDT"))
    submit(execution, request())

    with pytest.raises(PendingEntryConflictError, match="active pending"):
        submit(
            execution,
            request(setup_timestamp=START - timedelta(days=20), entry=99.0),
        )


def test_same_setup_is_not_resubmitted_after_manual_cancellation() -> None:
    broker = SimulatedBroker("BTCUSDT")
    execution = Execution(broker)
    trade_request = request()
    submit(execution, trade_request)
    execution.cancel_pending_entry()

    with pytest.raises(DuplicatePendingSetupError):
        submit(execution, trade_request)

    assert broker.submitted_entry_count == 1


def test_rejected_submission_is_remembered_for_deduplication() -> None:
    broker = SimulatedBroker("BTCUSDT")
    execution = Execution(broker)
    invalid_request = request(stop_loss=105.0)

    with pytest.raises(SimulatedOrderRejected):
        submit(execution, invalid_request)
    with pytest.raises(DuplicatePendingSetupError):
        submit(execution, invalid_request)

    assert broker.rejected_entry_count == 1


def test_same_setup_is_not_resubmitted_after_fill() -> None:
    broker = SimulatedBroker("BTCUSDT")
    execution = Execution(broker)
    trade_request = request()
    submit(execution, trade_request)
    broker.update_market(
        candle(1, open_price=100.0, high=101.0, low=99.0)
    )
    position = broker.get_open_position()
    assert position is not None
    broker.close_position(position)

    with pytest.raises(DuplicatePendingSetupError):
        submit(execution, trade_request)


def test_same_setup_is_not_resubmitted_after_expiry() -> None:
    broker = SimulatedBroker("BTCUSDT", pending_entry_ttl_candles=1)
    execution = Execution(broker)
    trade_request = request(entry=90.0, stop_loss=85.0)
    submit(execution, trade_request)
    broker.update_market(
        candle(1, open_price=100.0, high=101.0, low=99.0)
    )
    snapshot = execution.get_entry_order(
        build_order_link_id(
            build_setup_key(
                symbol="BTCUSDT",
                direction=trade_request.decision,
                setup_timestamp=trade_request.setup.timestamp,
                entry=trade_request.entry,
                stop_loss=trade_request.stop_loss,
                take_profit=trade_request.take_profit,
            )
        )
    )
    assert snapshot is not None
    assert snapshot.status == PendingEntryStatus.EXPIRED

    with pytest.raises(DuplicatePendingSetupError):
        submit(execution, trade_request)


def test_genuinely_new_setup_can_submit_after_terminal_entry() -> None:
    broker = SimulatedBroker("BTCUSDT")
    execution = Execution(broker)
    submit(execution, request())
    execution.cancel_pending_entry()

    pending = submit(
        execution,
        request(setup_timestamp=START - timedelta(days=20), entry=99.0),
    )

    assert pending.status == PendingEntryStatus.SUBMITTED
    assert broker.submitted_entry_count == 2


def test_recovered_order_link_id_blocks_deterministic_duplicate() -> None:
    broker = SimulatedBroker("BTCUSDT")
    execution = Execution(broker)
    trade_request = request()
    setup_key = build_setup_key(
        symbol="BTCUSDT",
        direction=trade_request.decision,
        setup_timestamp=trade_request.setup.timestamp,
        entry=trade_request.entry,
        stop_loss=trade_request.stop_loss,
        take_profit=trade_request.take_profit,
    )
    recovered_order_link_id = build_order_link_id(setup_key)

    execution.register_recovered_order_link_id(recovered_order_link_id)

    with pytest.raises(DuplicatePendingSetupError, match="recovered"):
        submit(execution, trade_request)
    assert broker.submitted_entry_count == 0


def test_recovered_order_link_id_registration_is_idempotent() -> None:
    execution = Execution(SimulatedBroker("BTCUSDT"))

    execution.register_recovered_order_link_id("QTR-recovered-order")
    execution.register_recovered_order_link_id("QTR-recovered-order")


def test_unrelated_setup_remains_allowed_after_recovery_registration() -> None:
    broker = SimulatedBroker("BTCUSDT")
    execution = Execution(broker)
    execution.register_recovered_order_link_id("QTR-unrelated-recovered-order")

    pending = submit(execution, request())

    assert pending.status == PendingEntryStatus.SUBMITTED
    assert broker.submitted_entry_count == 1


def test_recovery_registration_does_not_weaken_setup_key_deduplication() -> None:
    broker = SimulatedBroker("BTCUSDT")
    execution = Execution(broker)
    trade_request = request()
    execution.register_recovered_order_link_id("QTR-unrelated-recovered-order")
    submit(execution, trade_request)
    execution.cancel_pending_entry()

    with pytest.raises(DuplicatePendingSetupError, match="structural setup"):
        submit(execution, trade_request)
