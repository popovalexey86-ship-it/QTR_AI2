from datetime import datetime
from unittest.mock import Mock

import pytest

from core.decision import Decision
from core.position import Position
from core.position_monitor import PositionMonitor
from core.trade import Trade
from core.trade_journal import TradeJournal, TradeJournalWriteError
from core.trade_statistics import TradeStatistics


def make_position(ticket: str = "position-1") -> Position:
    return Position(
        ticket=ticket,
        decision=Decision.BUY,
        entry=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        volume=0.01,
        opened_at=datetime(2025, 1, 1),
    )


def make_trade(ticket: str = "trade-1", pnl: float = 5.0) -> Trade:
    return Trade(
        ticket=ticket,
        symbol="BTCUSDT",
        decision=Decision.BUY,
        entry=100.0,
        exit=105.0,
        volume=0.01,
        pnl=pnl,
        fees=0.1,
        opened_at=datetime(2025, 1, 1),
        closed_at=datetime(2025, 1, 2),
    )


def test_logs_new_open_position_once(monkeypatch):
    execution = Mock()
    position = make_position()
    execution.get_open_position.side_effect = [position, position]
    logger = Mock()
    monkeypatch.setattr("core.position_monitor.logger", logger)

    monitor = PositionMonitor(execution, TradeStatistics(), TradeJournal())
    monitor.update()
    monitor.update()

    assert monitor.position is position
    assert monitor.previous_position is position
    logger.info.assert_called_once()


def test_open_to_closed_adds_trade_and_preserves_previous_position():
    execution = Mock()
    position = make_position()
    trade = make_trade()
    execution.get_open_position.side_effect = [position, None]
    execution.get_last_closed_trade.return_value = trade
    statistics = TradeStatistics()
    journal = TradeJournal()
    monitor = PositionMonitor(execution, statistics, journal)

    monitor.update()
    monitor.update()

    assert monitor.position is None
    assert monitor.previous_position is position
    assert statistics.trades == (trade,)
    assert journal.trades == (trade,)
    assert execution.get_last_closed_trade.call_count == 1


def test_repeated_update_after_close_does_not_lookup_or_add_trade_again():
    execution = Mock()
    execution.get_open_position.side_effect = [make_position(), None, None]
    execution.get_last_closed_trade.return_value = make_trade()
    statistics = TradeStatistics()
    monitor = PositionMonitor(execution, statistics, TradeJournal())

    monitor.update()
    monitor.update()
    monitor.update()

    assert statistics.total_trades == 1
    assert execution.get_last_closed_trade.call_count == 1


def test_duplicate_closed_trade_ticket_is_not_added_twice():
    execution = Mock()
    execution.get_open_position.side_effect = [
        make_position("position-1"),
        None,
        make_position("position-2"),
        None,
    ]
    execution.get_last_closed_trade.return_value = make_trade("trade-1")
    statistics = TradeStatistics()
    monitor = PositionMonitor(execution, statistics, TradeJournal())

    for _ in range(4):
        monitor.update()

    assert statistics.total_trades == 1
    assert execution.get_last_closed_trade.call_count == 2


def test_missing_closed_trade_logs_warning_without_adding_statistics(monkeypatch):
    execution = Mock()
    execution.get_open_position.side_effect = [make_position(), None]
    execution.get_last_closed_trade.return_value = None
    logger = Mock()
    monkeypatch.setattr("core.position_monitor.logger", logger)
    statistics = TradeStatistics()
    monitor = PositionMonitor(execution, statistics, TradeJournal())

    monitor.update()
    monitor.update()

    assert statistics.total_trades == 0
    logger.warning.assert_called_once()


def test_existing_journal_trade_is_not_added_or_logged_again(monkeypatch):
    execution = Mock()
    trade = make_trade()
    journal = TradeJournal()
    journal.add_trade(trade)
    execution.get_open_position.side_effect = [make_position(), None]
    execution.get_last_closed_trade.return_value = trade
    statistics = TradeStatistics()
    logger = Mock()
    monkeypatch.setattr("core.position_monitor.logger", logger)
    monitor = PositionMonitor(execution, statistics, journal)

    monitor.update()
    monitor.update()

    assert statistics.trades == ()
    assert logger.info.call_count == 1


def test_journal_error_does_not_add_trade_to_statistics():
    class FailingJournal:
        @property
        def trades(self) -> tuple[Trade, ...]:
            return ()

        def add_trade(self, trade: Trade) -> bool:
            raise TradeJournalWriteError("disk unavailable")

    execution = Mock()
    execution.get_open_position.side_effect = [make_position(), None]
    execution.get_last_closed_trade.return_value = make_trade()
    statistics = TradeStatistics()
    monitor = PositionMonitor(execution, statistics, FailingJournal())

    monitor.update()

    with pytest.raises(TradeJournalWriteError, match="disk unavailable"):
        monitor.update()

    assert statistics.trades == ()
    assert monitor._last_closed_trade_ticket is None


def test_monitor_retries_trade_after_journal_recovers():
    class RecoveringJournal(TradeJournal):
        def __init__(self) -> None:
            super().__init__()
            self.attempts = 0

        def add_trade(self, trade: Trade) -> bool:
            self.attempts += 1
            if self.attempts == 1:
                raise TradeJournalWriteError("disk unavailable")
            return super().add_trade(trade)

    execution = Mock()
    trade = make_trade()
    execution.get_open_position.side_effect = [make_position(), None, None]
    execution.get_last_closed_trade.return_value = trade
    statistics = TradeStatistics()
    journal = RecoveringJournal()
    monitor = PositionMonitor(execution, statistics, journal)

    monitor.update()

    with pytest.raises(TradeJournalWriteError):
        monitor.update()

    monitor.update()

    assert journal.trades == (trade,)
    assert statistics.trades == (trade,)
    assert monitor._last_closed_trade_ticket == trade.ticket


def test_unexpected_runtime_error_is_not_logged_as_journal_write_error(monkeypatch):
    journal = Mock()
    journal.add_trade.side_effect = RuntimeError("programming error")
    execution = Mock()
    execution.get_open_position.side_effect = [make_position(), None]
    execution.get_last_closed_trade.return_value = make_trade()
    statistics = TradeStatistics()
    logger = Mock()
    monkeypatch.setattr("core.position_monitor.logger", logger)
    monitor = PositionMonitor(execution, statistics, journal)

    monitor.update()

    with pytest.raises(RuntimeError, match="programming error"):
        monitor.update()

    assert statistics.trades == ()
    assert monitor._last_closed_trade_ticket is None
    logger.exception.assert_not_called()
