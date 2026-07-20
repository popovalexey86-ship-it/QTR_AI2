from datetime import datetime

from core.decision import Decision
from core.trade import Trade
from core.trade_statistics import TradeStatistics


def make_trade(pnl: float, fees: float) -> Trade:
    return Trade(
        ticket=f"trade-{pnl}",
        symbol="BTCUSDT",
        decision=Decision.BUY,
        entry=100.0,
        exit=100.0 + pnl,
        volume=0.01,
        pnl=pnl,
        fees=fees,
        opened_at=datetime(2025, 1, 1),
        closed_at=datetime(2025, 1, 2),
    )


def test_trade_statistics_calculates_outcomes_and_pnl():
    statistics = TradeStatistics()
    win = make_trade(10.0, 0.1)
    loss = make_trade(-4.0, 0.2)
    breakeven = make_trade(0.0, 0.3)

    statistics.add_trade(win)
    statistics.add_trade(loss)
    statistics.add_trade(breakeven)

    assert statistics.trades == (win, loss, breakeven)
    assert statistics.total_trades == 3
    assert statistics.wins == 1
    assert statistics.losses == 1
    assert statistics.breakeven == 1
    assert statistics.total_pnl == 6.0
    assert statistics.total_fees == 0.6
    assert statistics.net_pnl == 6.0
