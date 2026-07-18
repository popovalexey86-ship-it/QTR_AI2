from core.decision import Decision
from core.position import Position
from core.trade_request import TradeRequest


class BybitOrderMapper:

    @staticmethod
    def to_order_request(
        request: TradeRequest,
    ) -> dict:

        side = "Buy" if request.decision == Decision.BUY else "Sell"

        return {
            "symbol": request.symbol,
            "side": side,
            "orderType": "Market",
            "qty": str(request.volume),
            "timeInForce": "IOC",
            "takeProfit": str(request.take_profit),
            "stopLoss": str(request.stop_loss),
        }

    @staticmethod
    def to_close_order_request(
        position: Position,
    ) -> dict:

        side = "Sell" if position.decision == Decision.BUY else "Buy"

        return {
            "symbol": position.symbol,
            "side": side,
            "orderType": "Market",
            "qty": str(position.volume),
            "timeInForce": "IOC",
            "reduceOnly": True,
        }
