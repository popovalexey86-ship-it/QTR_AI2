from datetime import UTC, datetime

from core.decision import Decision
from core.setup import Setup
from core.trade_request import TradeRequest
from core.trend import Trend

from infrastructure.bybit.bybit_order_mapper import BybitOrderMapper


def test_to_order_request():

    setup = Setup(
        index=0,
        timestamp=datetime.now(UTC),
        trend=Trend.BULLISH,
        entry=62000,
        stop_loss=61500,
    )

    request = TradeRequest(
        symbol="BTCUSDT",
        decision=Decision.BUY,
        entry=62000,
        stop_loss=61500,
        take_profit=63000,
        volume=0.01,
        setup=setup,
    )

    order = BybitOrderMapper.to_order_request(request)

    assert order["symbol"] == "BTCUSDT"
    assert order["side"] == "Buy"
    assert order["orderType"] == "Market"
    assert order["qty"] == "0.01"
    assert order["takeProfit"] == "63000"
    assert order["stopLoss"] == "61500"
