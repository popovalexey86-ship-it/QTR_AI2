from core.broker import Broker
from core.position import Position
from core.trade_request import TradeRequest


class Execution:

    def __init__(
        self,
        broker: Broker,
    ):
        self._broker = broker

    def execute(
        self,
        request: TradeRequest,
    ) -> Position:
        """
        Исполнить торговую заявку.
        """

        return self._broker.open_position(request)