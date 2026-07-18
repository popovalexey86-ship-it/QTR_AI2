from datetime import UTC, datetime

from core.decision import Decision
from core.position import Position


class BybitPositionMapper:

    @staticmethod
    def from_position(
        response: dict,
    ) -> Position:

        decision = (
            Decision.BUY
            if response["side"] == "Buy"
            else Decision.SELL
        )

        return Position(
            symbol=response["symbol"],
            decision=decision,
            entry=float(response["avgPrice"]),
            stop_loss=float(response["stopLoss"] or 0),
            take_profit=float(response["takeProfit"] or 0),
            volume=float(response["size"]),
            opened_at=datetime.now(UTC),
        )