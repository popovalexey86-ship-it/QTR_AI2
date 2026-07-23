from datetime import UTC, datetime

from core.decision import Decision
from core.position import Position
from core.trade_request import TradeRequest


class BybitPositionMapper:

    @staticmethod
    def from_order_response(
        response: dict,
        request: TradeRequest,
    ) -> Position:

        return Position(
            ticket=response["result"]["orderId"],
            symbol=request.symbol,
            decision=request.decision,
            entry=request.entry,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            volume=request.volume,
            opened_at=datetime.now(UTC),
        )

    @staticmethod
    def from_position(
        position: dict,
    ) -> Position:

        side = position["side"]

        decision = Decision.BUY if side == "Buy" else Decision.SELL

        return Position(
            ticket=position["positionIdx"],
            symbol=position["symbol"],
            decision=decision,
            entry=float(position["avgPrice"]),
            stop_loss=_optional_number(position.get("stopLoss")),
            take_profit=_optional_number(position.get("takeProfit")),
            volume=float(position["size"]),
            opened_at=datetime.now(UTC),
        )


def _optional_number(value: object) -> float:
    if value is None or value == "":
        return 0.0
    if not isinstance(value, (str, int, float)):
        raise TypeError("Optional position number has an unsupported type.")
    return float(value)
