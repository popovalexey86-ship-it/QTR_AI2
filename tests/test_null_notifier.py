from datetime import datetime

from core.decision import Decision
from core.position import Position
from core.trade import Trade
from core.trade_statistics import TradeStatistics
from infrastructure.null_notifier import NullNotifier


def test_null_notifier_accepts_open_and_closed_notifications():
    position = Position(
        ticket="position-1", symbol="BTCUSDT", decision=Decision.BUY,
        entry=100.0, stop_loss=95.0, take_profit=110.0, volume=0.01,
        opened_at=datetime(2025, 1, 1),
    )
    trade = Trade(
        ticket="trade-1", symbol="BTCUSDT", decision=Decision.BUY,
        entry=100.0, exit=105.0, volume=0.01, pnl=5.0, fees=0.1,
        opened_at=datetime(2025, 1, 1), closed_at=datetime(2025, 1, 2),
    )
    notifier = NullNotifier()

    assert notifier.position_opened(position) is None
    assert notifier.trade_closed(trade, TradeStatistics()) is None
