from datetime import datetime

from core.decision import Decision
from core.trade import Trade


class BybitTradeMapper:

    @staticmethod
    def from_closed_pnl(data: dict) -> Trade:

        side = data["side"]

        decision = (
            Decision.BUY
            if side == "Buy"
            else Decision.SELL
        )

        fee = float(data["openFee"]) + float(data["closeFee"])

        closed_at = datetime.fromtimestamp(
            int(data["createdTime"]) / 1000
        )

        return Trade(
            ticket=data["orderId"],
            symbol=data["symbol"],
            decision=decision,
            entry=float(data["avgEntryPrice"]),
            exit=float(data["avgExitPrice"]),
            volume=float(data["qty"]),
            pnl=float(data["closedPnl"]),
            fees=fee,
            opened_at=closed_at,      # временно
            closed_at=closed_at,
        )