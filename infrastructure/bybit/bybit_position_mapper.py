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
            stop_loss=float(position.get("stopLoss", 0)),
            take_profit=float(position.get("takeProfit", 0)),
            volume=float(position["size"]),
            opened_at=datetime.now(UTC),
        )