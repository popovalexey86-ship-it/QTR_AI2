from decimal import Decimal
import math
import re

from core.decision import Decision
from core.exceptions import BrokerError
from core.trade_request import TradeRequest


class BybitEntryOrderMappingError(BrokerError):
    """Raised when a pending entry cannot be mapped safely for Bybit."""


class BybitEntryOrderMapper:
    """Map a domain request to a linear resting limit order."""

    @staticmethod
    def to_order_request(
        request: TradeRequest,
        *,
        symbol: str,
        order_link_id: str,
    ) -> dict[str, object]:
        normalized_symbol = symbol.strip()
        if not normalized_symbol:
            raise BybitEntryOrderMappingError(
                "Pending entry symbol cannot be empty."
            )
        _validate_order_link_id(order_link_id)

        if request.decision == Decision.BUY:
            side = "Buy"
        elif request.decision == Decision.SELL:
            side = "Sell"
        else:
            raise BybitEntryOrderMappingError(
                "Pending entry direction must be BUY or SELL."
            )

        _validate_positive_finite(request.entry, "entry")
        _validate_positive_finite(request.stop_loss, "stop loss")
        _validate_positive_finite(request.take_profit, "take profit")
        _validate_positive_finite(request.volume, "volume")
        _validate_protective_levels(request)

        return {
            "symbol": normalized_symbol,
            "side": side,
            "orderType": "Limit",
            "qty": _normalize_number(request.volume),
            "price": _normalize_number(request.entry),
            "timeInForce": "GTC",
            "positionIdx": 0,
            "orderLinkId": order_link_id,
            "reduceOnly": False,
            "takeProfit": _normalize_number(request.take_profit),
            "stopLoss": _normalize_number(request.stop_loss),
            "tpslMode": "Full",
            "tpOrderType": "Market",
            "slOrderType": "Market",
            "tpTriggerBy": "LastPrice",
            "slTriggerBy": "LastPrice",
        }


def _validate_order_link_id(order_link_id: str) -> None:
    if (
        not order_link_id
        or len(order_link_id) > 36
        or re.fullmatch(r"[A-Za-z0-9_-]+", order_link_id) is None
    ):
        raise BybitEntryOrderMappingError(
            "Order link ID must be ASCII-safe and at most 36 characters."
        )


def _validate_positive_finite(value: float, field_name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise BybitEntryOrderMappingError(
            f"Pending entry {field_name} must be finite and positive."
        )


def _validate_protective_levels(request: TradeRequest) -> None:
    if request.decision == Decision.BUY:
        valid = request.stop_loss < request.entry < request.take_profit
    else:
        valid = request.take_profit < request.entry < request.stop_loss
    if not valid:
        raise BybitEntryOrderMappingError(
            "Pending entry protective levels are invalid."
        )


def _normalize_number(value: float) -> str:
    return format(Decimal(str(value)).normalize(), "f")
