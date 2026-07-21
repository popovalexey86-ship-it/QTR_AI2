from dataclasses import replace
from datetime import UTC, datetime
import math

import pytest

from core.decision import Decision
from core.setup import Setup
from core.trade_request import TradeRequest
from core.trend import Trend
from infrastructure.bybit.bybit_entry_order_mapper import (
    BybitEntryOrderMapper,
    BybitEntryOrderMappingError,
)


def request(decision: Decision) -> TradeRequest:
    bullish = decision == Decision.BUY
    setup = Setup(
        index=1,
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        trend=Trend.BULLISH if bullish else Trend.BEARISH,
        entry=62000.0,
        stop_loss=61500.0 if bullish else 62500.0,
    )
    return TradeRequest(
        symbol="REQUEST_SYMBOL_MUST_NOT_WIN",
        decision=decision,
        entry=62000.0,
        stop_loss=61500.0 if bullish else 62500.0,
        take_profit=63000.0 if bullish else 61000.0,
        volume=0.0100,
        setup=setup,
    )


@pytest.mark.parametrize(
    ("decision", "side", "stop_loss", "take_profit"),
    [
        (Decision.BUY, "Buy", "61500", "63000"),
        (Decision.SELL, "Sell", "62500", "61000"),
    ],
)
def test_maps_resting_limit_entry_with_attached_last_price_protection(
    decision: Decision,
    side: str,
    stop_loss: str,
    take_profit: str,
) -> None:
    mapped = BybitEntryOrderMapper.to_order_request(
        request(decision),
        symbol="BTCUSDT",
        order_link_id="QTR-0123456789abcdef",
    )

    assert mapped == {
        "symbol": "BTCUSDT",
        "side": side,
        "orderType": "Limit",
        "qty": "0.01",
        "price": "62000",
        "timeInForce": "GTC",
        "positionIdx": 0,
        "orderLinkId": "QTR-0123456789abcdef",
        "reduceOnly": False,
        "takeProfit": take_profit,
        "stopLoss": stop_loss,
        "tpslMode": "Full",
        "tpOrderType": "Market",
        "slOrderType": "Market",
        "tpTriggerBy": "LastPrice",
        "slTriggerBy": "LastPrice",
    }
    assert "triggerPrice" not in mapped
    assert "IOC" not in mapped.values()


@pytest.mark.parametrize(
    "trade_request",
    [
        replace(request(Decision.BUY), stop_loss=62000.0),
        replace(request(Decision.BUY), take_profit=62000.0),
        replace(request(Decision.SELL), stop_loss=62000.0),
        replace(request(Decision.SELL), take_profit=62000.0),
    ],
)
def test_invalid_protective_levels_are_rejected(
    trade_request: TradeRequest,
) -> None:
    with pytest.raises(BybitEntryOrderMappingError, match="protective"):
        BybitEntryOrderMapper.to_order_request(
            trade_request,
            symbol="BTCUSDT",
            order_link_id="QTR-order",
        )


@pytest.mark.parametrize(
    "trade_request",
    [
        replace(request(Decision.BUY), entry=math.inf),
        replace(request(Decision.BUY), stop_loss=math.nan),
        replace(request(Decision.BUY), take_profit=-1.0),
        replace(request(Decision.BUY), volume=math.inf),
    ],
)
def test_non_finite_or_non_positive_numbers_are_rejected(
    trade_request: TradeRequest,
) -> None:
    with pytest.raises(BybitEntryOrderMappingError, match="finite and positive"):
        BybitEntryOrderMapper.to_order_request(
            trade_request,
            symbol="BTCUSDT",
            order_link_id="QTR-order",
        )


@pytest.mark.parametrize(
    "order_link_id",
    ["", "QTR:invalid", "QTR space", "QTR-é", "Q" * 37],
)
def test_order_link_id_contract_is_enforced(order_link_id: str) -> None:
    with pytest.raises(BybitEntryOrderMappingError, match="ASCII-safe"):
        BybitEntryOrderMapper.to_order_request(
            request(Decision.BUY),
            symbol="BTCUSDT",
            order_link_id=order_link_id,
        )


def test_mapping_errors_do_not_echo_secret_like_input() -> None:
    secret_like_id = "token:sensitive-secret"

    with pytest.raises(BybitEntryOrderMappingError) as error:
        BybitEntryOrderMapper.to_order_request(
            request(Decision.BUY),
            symbol="BTCUSDT",
            order_link_id=secret_like_id,
        )

    assert "sensitive-secret" not in str(error.value)
    assert "sensitive-secret" not in repr(BybitEntryOrderMapper())


def test_empty_authoritative_symbol_is_rejected() -> None:
    with pytest.raises(BybitEntryOrderMappingError, match="symbol"):
        BybitEntryOrderMapper.to_order_request(
            request(Decision.BUY),
            symbol=" ",
            order_link_id="QTR-order",
        )


def test_skip_direction_is_rejected_even_for_mutated_runtime_input() -> None:
    trade_request = request(Decision.BUY)
    object.__setattr__(trade_request, "decision", Decision.SKIP)

    with pytest.raises(BybitEntryOrderMappingError, match="BUY or SELL"):
        BybitEntryOrderMapper.to_order_request(
            trade_request,
            symbol="BTCUSDT",
            order_link_id="QTR-order",
        )


def test_exact_36_character_order_link_id_is_allowed() -> None:
    order_link_id = "Q" * 36

    mapped = BybitEntryOrderMapper.to_order_request(
        request(Decision.BUY),
        symbol="BTCUSDT",
        order_link_id=order_link_id,
    )

    assert mapped["orderLinkId"] == order_link_id
