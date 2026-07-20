from core.trade import Trade


class TradeStatistics:
    """In-memory statistics for closed trades.

    The Bybit mapper stores ``Trade.pnl`` from Bybit's ``closedPnl`` field.
    That value already includes opening and closing fees, so ``net_pnl`` is
    the sum of ``pnl`` and must not subtract ``total_fees`` again.
    """

    def __init__(self) -> None:
        self._trades: list[Trade] = []

    def add_trade(self, trade: Trade) -> None:
        self._trades.append(trade)

    @property
    def trades(self) -> tuple[Trade, ...]:
        return tuple(self._trades)

    @property
    def total_trades(self) -> int:
        return len(self._trades)

    @property
    def wins(self) -> int:
        return sum(trade.pnl > 0 for trade in self._trades)

    @property
    def losses(self) -> int:
        return sum(trade.pnl < 0 for trade in self._trades)

    @property
    def breakeven(self) -> int:
        return sum(trade.pnl == 0 for trade in self._trades)

    @property
    def total_pnl(self) -> float:
        return sum(trade.pnl for trade in self._trades)

    @property
    def total_fees(self) -> float:
        return sum(trade.fees for trade in self._trades)

    @property
    def net_pnl(self) -> float:
        return self.total_pnl
