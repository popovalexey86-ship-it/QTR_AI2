from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, call

import pytest

from backtesting.simulated_broker import SimulatedBroker, SimulatedOrderRejected
from core.analysis_context import AnalysisContext
from core.candle import Candle
from core.decision_engine import DecisionEngine
from core.execution import Execution
from core.exceptions import TemporaryTransportError
from core.market_data import MarketData
from core.pending_entry import PendingEntryStatus, build_setup_key
from core.position_monitor import PositionMonitor
from core.risk_manager import RiskManager
from core.setup import Setup
from core.trade_journal import TradeJournal
from core.trade_statistics import TradeStatistics
from core.trend import Trend
from engine.trading_engine import TradingEngine
from infrastructure.null_notifier import NullNotifier
from core.notification import NotificationError
from tests.test_telegram_notifier import make_pending_event
from strategies.strategy import Strategy


START = datetime(2025, 1, 1, tzinfo=UTC)
OLD_SETUP_TIME = START - timedelta(days=30)


class ScriptedStrategy(Strategy):
    def __init__(self, setups: list[Setup | None]) -> None:
        self._setups = setups
        self.calls = 0

    def analyze(self, market_data: MarketData) -> AnalysisContext:
        setup = (
            self._setups[self.calls]
            if self.calls < len(self._setups)
            else None
        )
        self.calls += 1
        return AnalysisContext(market_data=market_data, setup=setup)


def setup(
    *,
    timestamp: datetime = OLD_SETUP_TIME,
    entry: float = 100.0,
    stop_loss: float = 95.0,
) -> Setup:
    return Setup(
        index=1,
        timestamp=timestamp,
        trend=Trend.BULLISH,
        entry=entry,
        stop_loss=stop_loss,
    )


def market_data(
    minute: int,
    *,
    symbol: str = "BTCUSDT",
    open_price: float = 100.0,
    high: float = 101.0,
    low: float = 99.0,
) -> MarketData:
    item = Candle(
        timestamp=START + timedelta(minutes=minute),
        open=open_price,
        high=high,
        low=low,
        close=open_price,
        volume=1.0,
        index=minute,
    )
    return MarketData(symbol=symbol, timeframe="1m", candles=[item])


def engine_parts(
    strategy: Strategy,
    *,
    symbol: str = "BTCUSDT",
    ttl: int = 4,
) -> tuple[TradingEngine, Execution, SimulatedBroker]:
    broker = SimulatedBroker(symbol, pending_entry_ttl_candles=ttl)
    execution = Execution(broker)
    monitor = PositionMonitor(
        execution,
        TradeStatistics(),
        TradeJournal(),
        NullNotifier(),
    )
    engine = TradingEngine(
        strategy=strategy,
        decision_engine=DecisionEngine(),
        risk_manager=RiskManager(
            risk_reward=2.0,
            symbol="BTCUSDT",
            volume=0.01,
        ),
        execution=execution,
        position_monitor=monitor,
    )
    return engine, execution, broker


def test_setup_creates_pending_not_position_using_signal_candle_time() -> None:
    structural_setup = setup()
    strategy = ScriptedStrategy([structural_setup])
    engine, _, broker = engine_parts(strategy)
    signal_data = market_data(10)

    engine.process(signal_data)

    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.signal_timestamp == signal_data.last.timestamp
    assert pending.signal_timestamp != structural_setup.timestamp
    assert broker.get_open_position() is None


def test_old_setup_timestamp_cannot_enable_signal_candle_fill() -> None:
    strategy = ScriptedStrategy([setup()])
    engine, _, broker = engine_parts(strategy)
    signal_data = market_data(10, high=111.0, low=94.0)
    engine.process(signal_data)

    broker.update_market(signal_data.last)

    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.status == PendingEntryStatus.SUBMITTED
    assert broker.get_open_position() is None


def test_active_pending_entry_suppresses_later_analysis_and_submission() -> None:
    strategy = ScriptedStrategy(
        [setup(), setup(timestamp=OLD_SETUP_TIME + timedelta(days=1), entry=99.0)]
    )
    engine, _, broker = engine_parts(strategy)

    engine.process(market_data(1))
    engine.process(market_data(2))

    assert strategy.calls == 1
    assert broker.submitted_entry_count == 1


def test_open_position_suppresses_pending_submission() -> None:
    strategy = ScriptedStrategy([setup()])
    engine, _, broker = engine_parts(strategy)
    broker.update_market(market_data(0).last)
    broker.open_position(
        RiskManager(
            risk_reward=2.0,
            symbol="BTCUSDT",
            volume=0.01,
        ).build(setup(), DecisionEngine().decide(setup()))
    )

    engine.process(market_data(1))

    assert strategy.calls == 0
    assert broker.get_pending_entry() is None


def test_same_setup_is_not_recreated_after_expiry() -> None:
    repeated_setup = setup(entry=90.0, stop_loss=85.0)
    strategy = ScriptedStrategy([repeated_setup, repeated_setup])
    engine, _, broker = engine_parts(strategy, ttl=1)
    engine.process(market_data(0))

    next_data = market_data(1, open_price=100.0, high=101.0, low=99.0)
    broker.update_market(next_data.last)
    engine.process(next_data)

    assert broker.expired_entry_count == 1
    assert broker.submitted_entry_count == 1
    assert broker.get_pending_entry() is None


def test_same_setup_is_not_recreated_after_rejection() -> None:
    invalid_setup = setup(stop_loss=105.0)
    strategy = ScriptedStrategy([invalid_setup, invalid_setup])
    engine, _, broker = engine_parts(strategy)

    with pytest.raises(SimulatedOrderRejected):
        engine.process(market_data(0))
    engine.process(market_data(1))

    assert broker.rejected_entry_count == 1
    assert broker.submitted_entry_count == 1


def test_new_setup_may_submit_after_terminal_completion() -> None:
    first_setup = setup()
    second_setup = setup(
        timestamp=OLD_SETUP_TIME + timedelta(days=1),
        entry=99.0,
        stop_loss=94.0,
    )
    strategy = ScriptedStrategy([first_setup, second_setup])
    engine, execution, broker = engine_parts(strategy)
    engine.process(market_data(0))
    execution.cancel_pending_entry()

    engine.process(market_data(1))

    assert broker.submitted_entry_count == 2
    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.request.entry == 99.0


def test_market_data_symbol_is_authoritative_for_setup_identity() -> None:
    structural_setup = setup()
    strategy = ScriptedStrategy([structural_setup])
    engine, _, broker = engine_parts(strategy, symbol="ETHUSDT")
    data = market_data(1, symbol="ETHUSDT")

    engine.process(data)

    pending = broker.get_pending_entry()
    assert pending is not None
    assert pending.setup_key == build_setup_key(
        symbol="ETHUSDT",
        direction=pending.request.decision,
        setup_timestamp=structural_setup.timestamp,
        entry=pending.request.entry,
        stop_loss=pending.request.stop_loss,
        take_profit=pending.request.take_profit,
    )


def test_runtime_recovery_and_poll_use_explicit_facade_order() -> None:
    execution = Mock()
    position_monitor = Mock()
    engine = TradingEngine(
        strategy=Mock(),
        decision_engine=Mock(),
        risk_manager=Mock(),
        execution=execution,
        position_monitor=position_monitor,
    )
    parent = Mock()
    parent.attach_mock(execution.recover_pending_entry, "recover")
    parent.attach_mock(execution.refresh_pending_entry, "refresh")
    parent.attach_mock(position_monitor.update, "monitor")

    engine.recover_runtime_state()
    engine.poll_runtime_state()

    assert parent.mock_calls == [
        call.recover(),
        call.monitor(),
        call.refresh(),
        call.monitor(),
    ]


def test_position_timeout_does_not_block_pending_refresh() -> None:
    execution = Mock()
    expected_pending = Mock()
    execution.refresh_pending_entry.return_value = expected_pending
    position_monitor = Mock()
    position_monitor.update.side_effect = TemporaryTransportError(
        "temporary position failure"
    )
    engine = TradingEngine(
        strategy=Mock(),
        decision_engine=Mock(),
        risk_manager=Mock(),
        execution=execution,
        position_monitor=position_monitor,
    )

    with pytest.raises(TemporaryTransportError):
        engine.poll_runtime_state()

    execution.refresh_pending_entry.assert_called_once_with()
    position_monitor.update.assert_called_once_with()


def test_trading_engine_age_facade_delegates_without_bybit_dependency() -> None:
    execution = Mock()
    expected = Mock()
    execution.age_pending_entry.return_value = expected
    engine = TradingEngine(
        strategy=Mock(),
        decision_engine=Mock(),
        risk_manager=Mock(),
        execution=execution,
        position_monitor=Mock(),
    )
    timestamps = (START + timedelta(minutes=15),)

    result = engine.age_pending_entry(timestamps, ttl_candles=4)

    assert result is expected
    execution.age_pending_entry.assert_called_once_with(
        timestamps,
        ttl_candles=4,
    )


def test_pending_notification_failure_does_not_block_later_events() -> None:
    execution = Mock()
    expected_pending = Mock()
    execution.refresh_pending_entry.return_value = expected_pending
    events = (
        make_pending_event(PendingEntryStatus.WORKING),
        make_pending_event(PendingEntryStatus.CANCEL_REQUESTED),
    )
    execution.drain_pending_entry_events.return_value = events
    notifier = Mock()
    notifier.pending_entry_event.side_effect = [
        NotificationError("secret transport details"),
        None,
    ]
    engine = TradingEngine(
        strategy=Mock(),
        decision_engine=Mock(),
        risk_manager=Mock(),
        execution=execution,
        position_monitor=Mock(),
        notifier=notifier,
    )

    result = engine.poll_runtime_state()

    assert result is expected_pending
    assert notifier.pending_entry_event.call_args_list == [
        call(events[0]),
        call(events[1]),
    ]
    execution.refresh_pending_entry.assert_called_once_with()
