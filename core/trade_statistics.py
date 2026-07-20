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

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.wins / self.total_trades

    @property
    def average_win(self) -> float:
        if self.wins == 0:
            return 0.0
        return sum(trade.pnl for trade in self._trades if trade.pnl > 0) / self.wins

    @property
    def average_loss(self) -> float:
        if self.losses == 0:
            return 0.0
        return sum(trade.pnl for trade in self._trades if trade.pnl < 0) / self.losses

    @property
    def profit_factor(self) -> float:
        gross_loss = -sum(trade.pnl for trade in self._trades if trade.pnl < 0)
        if gross_loss == 0:
            return 0.0
        gross_profit = sum(trade.pnl for trade in self._trades if trade.pnl > 0)
        return gross_profit / gross_loss

    @property
    def expectancy(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.total_pnl / self.total_trades
