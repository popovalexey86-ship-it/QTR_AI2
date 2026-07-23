from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from core.decision import Decision
from core.setup import Setup
from core.trade_request import TradeRequest
from core.trend import Trend

from infrastructure.bybit.bybit_broker import BybitBroker
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


def _position_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "positionIdx": "0",
        "symbol": "BTCUSDT",
        "side": "Buy",
        "avgPrice": "100",
        "size": "1",
        "stopLoss": "95",
        "takeProfit": "110",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    ("overrides", "expected_stop_loss", "expected_take_profit"),
    [
        ({"stopLoss": ""}, 0.0, 110.0),
        ({"takeProfit": ""}, 95.0, 0.0),
        ({"stopLoss": "", "takeProfit": ""}, 0.0, 0.0),
        ({"stopLoss": None, "takeProfit": None}, 0.0, 0.0),
        ({"stopLoss": 94.5, "takeProfit": "111.5"}, 94.5, 111.5),
    ],
    ids=(
        "empty-stop-loss",
        "empty-take-profit",
        "both-empty",
        "none-values",
        "normal-numeric-values",
    ),
)
def test_from_position_normalizes_optional_tp_sl_values(
    overrides: dict[str, object],
    expected_stop_loss: float,
    expected_take_profit: float,
) -> None:
    position = BybitPositionMapper.from_position(
        _position_payload(**overrides)
    )

    assert position.stop_loss == expected_stop_loss
    assert position.take_profit == expected_take_profit


def test_from_position_normalizes_missing_tp_sl_keys() -> None:
    payload = _position_payload()
    del payload["stopLoss"]
    del payload["takeProfit"]

    position = BybitPositionMapper.from_position(payload)

    assert position.stop_loss == 0.0
    assert position.take_profit == 0.0


def test_successful_position_response_with_empty_tp_sl_does_not_fail() -> None:
    client = Mock()
    client.get_positions.return_value = {
        "retCode": 0,
        "result": {
            "list": [
                _position_payload(stopLoss="", takeProfit=""),
            ]
        },
    }
    broker = BybitBroker(
        client=client,
        category="linear",
        symbol="BTCUSDT",
    )

    positions = broker.get_positions()

    assert len(positions) == 1
    assert positions[0].stop_loss == 0.0
    assert positions[0].take_profit == 0.0
