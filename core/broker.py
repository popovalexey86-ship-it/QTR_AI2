from abc import ABC, abstractmethod

from core.position import Position
from core.trade_request import TradeRequest


class Broker(ABC):

    @abstractmethod
    def open_position(
        self,
        request: TradeRequest,
    ) -> Position:
        ...

    @abstractmethod
    def close_position(
        self,
        position: Position,
    ) -> None:
        ...

    @abstractmethod
    def get_positions(
        self,
    ) -> list[Position]:
        ...