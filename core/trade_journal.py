from typing import Protocol

from core.trade import Trade


class TradeJournalWriteError(RuntimeError):
    """Raised when a trade cannot be persisted by a journal adapter."""


class TradeJournalPort(Protocol):
    def add_trade(self, trade: Trade) -> bool: ...

    @property
    def trades(self) -> tuple[Trade, ...]: ...


class TradeJournal:
    """In-memory journal of unique closed trades."""

    def __init__(self) -> None:
        self._trades: list[Trade] = []
        self._tickets: set[str] = set()

    def add_trade(self, trade: Trade) -> bool:
        if trade.ticket in self._tickets:
            return False

        self._trades.append(trade)
        self._tickets.add(trade.ticket)
        return True

    @property
    def trades(self) -> tuple[Trade, ...]:
        return tuple(self._trades)
