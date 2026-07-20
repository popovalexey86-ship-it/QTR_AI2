from core.broker import Broker
from core.position import Position
from core.trade import Trade
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

    def get_open_position(
        self,
    ) -> Position | None:
        """
        Возвращает текущую открытую позицию.
        """
        return self._broker.get_open_position()

    def get_last_closed_trade(
        self,
    ) -> Trade | None:
        """
        Возвращает последнюю закрытую сделку.
        """
        return self._broker.get_last_closed_trade()