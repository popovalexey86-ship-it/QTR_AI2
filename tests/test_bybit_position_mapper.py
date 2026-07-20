from datetime import UTC, datetime

from core.decision import Decision
from core.setup import Setup
from core.trade_request import TradeRequest
from core.trend import Trend

from infrastructure.bybit.bybit_position_mapper import BybitPositionMapper


def test_from_order_response():

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

    response = {
        "result": {
            "orderId": "123456",
        }
    }

    position = BybitPositionMapper.from_order_response(
        response=response,
        request=request,
    )

    assert position.ticket == "123456"
    assert position.decision == Decision.BUY
    assert position.entry == 62000
    assert position.stop_loss == 61500
    assert position.take_profit == 63000
    assert position.volume == 0.01
