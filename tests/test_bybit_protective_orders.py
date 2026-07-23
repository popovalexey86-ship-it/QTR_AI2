from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.decision import Decision
from core.position import Position
from infrastructure.bybit.bybit_pending_entry_store import BybitPendingEntryStore
from tests.test_bybit_pending_broker import _broker, _query_response


def _position(decision: Decision) -> Position:
    return Position(
        ticket="position-1",
        symbol="BTCUSDT",
        decision=decision,
        entry=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        volume=1.0,
        opened_at=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
    )


def _order(
    *,
    side: str,
    stop_order_type: str,
    reduce_only: bool = False,
    close_on_trigger: bool = False,
    symbol: str = "BTCUSDT",
) -> dict[str, object]:
    return {
        "orderLinkId": "",
        "symbol": symbol,
        "side": side,
        "orderType": "Market",
        "stopOrderType": stop_order_type,
        "reduceOnly": reduce_only,
        "closeOnTrigger": close_on_trigger,
    }


def test_short_position_tp_sl_orders_are_protective_and_allowed() -> None:
    broker, client = _broker()
    client.list_open_orders.return_value = _query_response(
        _order(
            side="Buy",
            stop_order_type="TakeProfit",
            reduce_only=True,
        ),
        _order(
            side="Buy",
            stop_order_type="StopLoss",
            close_on_trigger=True,
        ),
    )

    counts = broker.inspect_active_order_counts([_position(Decision.SELL)])

    assert counts == (0, 2, 0)


def test_long_position_tp_sl_orders_are_protective_and_allowed() -> None:
    broker, client = _broker()
    client.list_open_orders.return_value = _query_response(
        _order(
            side="Sell",
            stop_order_type="TakeProfit",
            reduce_only=True,
        ),
        _order(
            side="Sell",
            stop_order_type="StopLoss",
            close_on_trigger=True,
        ),
    )

    counts = broker.inspect_active_order_counts([_position(Decision.BUY)])

    assert counts == (0, 2, 0)


def test_unrelated_limit_order_remains_foreign_and_blocking() -> None:
    broker, client = _broker()
    client.list_open_orders.return_value = _query_response(
        {
            **_order(side="Sell", stop_order_type=""),
            "orderType": "Limit",
        }
    )

    counts = broker.inspect_active_order_counts([_position(Decision.BUY)])

    assert counts == (0, 0, 1)


def test_foreign_reduce_only_non_tpsl_order_requires_review() -> None:
    broker, client = _broker()
    client.list_open_orders.return_value = _query_response(
        _order(
            side="Sell",
            stop_order_type="",
            reduce_only=True,
        )
    )

    counts = broker.inspect_active_order_counts([_position(Decision.BUY)])

    assert counts == (0, 0, 1)


def test_tpsl_order_without_open_position_remains_foreign() -> None:
    broker, client = _broker()
    client.list_open_orders.return_value = _query_response(
        _order(
            side="Sell",
            stop_order_type="StopLoss",
            close_on_trigger=True,
        )
    )

    counts = broker.inspect_active_order_counts([])

    assert counts == (0, 0, 1)


@pytest.mark.parametrize(
    ("side", "symbol"),
    [
        ("Buy", "BTCUSDT"),
        ("Sell", "ETHUSDT"),
    ],
)
def test_tpsl_with_wrong_closing_side_or_symbol_remains_foreign(
    side: str,
    symbol: str,
) -> None:
    broker, client = _broker()
    client.list_open_orders.return_value = _query_response(
        _order(
            side=side,
            symbol=symbol,
            stop_order_type="StopLoss",
            reduce_only=True,
        )
    )

    counts = broker.inspect_active_order_counts([_position(Decision.BUY)])

    assert counts == (0, 0, 1)


def test_startup_recovery_allows_position_with_exchange_protection(
    tmp_path: Path,
) -> None:
    store = BybitPendingEntryStore(tmp_path / "pending.json")
    broker, client = _broker(pending_entry_store=store)
    client.list_open_orders.return_value = _query_response(
        _order(
            side="Sell",
            stop_order_type="TakeProfit",
            reduce_only=True,
        ),
        _order(
            side="Sell",
            stop_order_type="StopLoss",
            close_on_trigger=True,
        ),
    )
    client.get_positions.return_value = {
        "retCode": 0,
        "result": {
            "list": [
                {
                    "size": "1",
                    "side": "Buy",
                    "positionIdx": "0",
                    "symbol": "BTCUSDT",
                    "avgPrice": "100",
                    "stopLoss": "95",
                    "takeProfit": "110",
                }
            ]
        },
    }

    assert broker.recover_pending_entry() is None
    assert broker.get_pending_entry() is None
