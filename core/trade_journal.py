from core.trade import Trade


class TradeJournal:
    """In-memory journal of closed trades."""

    def __init__(self) -> None:
        self._trades: list[Trade] = []

    def add_trade(self, trade: Trade) -> None:
        self._trades.append(trade)

    @property
    def trades(self) -> tuple[Trade, ...]:
        return tuple(self._trades)
