from datetime import datetime

from core.decision import Decision
from core.trade import Trade
from core.trade_journal import TradeJournal


def test_trade_journal_adds_trade():
    trade = Trade(
        ticket="trade-1",
        symbol="BTCUSDT",
        decision=Decision.BUY,
        entry=100.0,
        exit=105.0,
        volume=0.01,
        pnl=5.0,
        fees=0.1,
        opened_at=datetime(2025, 1, 1),
        closed_at=datetime(2025, 1, 2),
    )
    journal = TradeJournal()

    journal.add_trade(trade)

    assert journal.trades == (trade,)
