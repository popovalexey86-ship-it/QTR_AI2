from abc import ABC, abstractmethod
from datetime import datetime

from core.entry_order import EntryOrderAcknowledgement, EntryOrderSnapshot
from core.pending_entry import PendingEntry
from core.trade import Trade
from core.position import Position
from core.trade_request import TradeRequest


class Broker(ABC):

    @abstractmethod
    def open_position(
        self,
        request: TradeRequest,
    ) -> Position: ...

    @abstractmethod
    def close_position(
        self,
        position: Position,
    ) -> None: ...

    @abstractmethod
    def get_positions(
        self,
    ) -> list[Position]: ...

    @abstractmethod
    def get_open_position(
        self,
    )  -> Position | None: ...

    @abstractmethod
    def get_last_closed_trade(
        self,
    ) -> Trade | None:...

    def submit_entry(
        self,
        request: TradeRequest,
        *,
        order_link_id: str,
        setup_key: str,
        signal_timestamp: datetime,
    ) -> EntryOrderAcknowledgement:
        raise NotImplementedError(
            "Pending entry submission is not supported by this broker."
        )

    def get_entry_order(
        self,
        order_link_id: str,
    ) -> EntryOrderSnapshot | None:
        return None

    def cancel_entry(self, order_link_id: str) -> None:
        raise NotImplementedError(
            "Pending entry cancellation is not supported by this broker."
        )

    def get_pending_entry(self) -> PendingEntry | None:
        return None
