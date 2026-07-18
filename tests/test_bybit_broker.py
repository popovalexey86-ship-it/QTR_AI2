from datetime import UTC, datetime
from unittest.mock import Mock

from core.decision import Decision
from core.position import Position
from core.setup import Setup
from core.trade_request import TradeRequest
from core.trend import Trend

from infrastructure.bybit.bybit_broker import BybitBroker


def test_open_position():

    client = Mock()

    client.place_order.return_value = {
        "result": {
            "orderId": "123456",
        }
    }

    broker = BybitBroker(
        client=client,
        category="linear",
        symbol="BTCUSDT",
    )

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

    position = broker.open_position(request)

    assert isinstance(position, Position)
    assert position.ticket == 123456
    assert position.decision == Decision.BUY
    assert position.entry == 62000
    assert position.volume == 0.01


def test_get_positions():

    client = Mock()

    client.get_positions.return_value = {
        "result": {
            "list": [],
        }
    }

    broker = BybitBroker(
        client=client,
        category="linear",
        symbol="BTCUSDT",
    )

    positions = broker.get_positions()

    assert positions == []

    client.get_positions.assert_called_once_with(
        category="linear",
        symbol="BTCUSDT",
    )
