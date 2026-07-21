from datetime import datetime

from core.broker import Broker
from core.entry_order import EntryOrderSnapshot
from core.exceptions import (
    DuplicatePendingSetupError,
    PendingEntryConflictError,
    PendingEntrySubmissionError,
)
from core.pending_entry import (
    PendingEntry,
    build_order_link_id,
    build_setup_key,
)
from core.position import Position
from core.trade import Trade
from core.trade_request import TradeRequest


class Execution:

    def __init__(
        self,
        broker: Broker,
    ):
        self._broker = broker
        self._submitted_setup_keys: set[str] = set()
        self._recovered_order_link_ids: set[str] = set()

    def register_recovered_order_link_id(self, order_link_id: str) -> None:
        normalized_order_link_id = order_link_id.strip()
        if not normalized_order_link_id:
            raise ValueError("Recovered order link ID cannot be empty.")
        self._recovered_order_link_ids.add(normalized_order_link_id)

    def execute(
        self,
        request: TradeRequest,
    ) -> Position:
        """
        Исполнить торговую заявку.
        """
        return self._broker.open_position(request)

    def submit_pending_entry(
        self,
        request: TradeRequest,
        *,
        setup_timestamp: datetime,
        signal_timestamp: datetime,
        authoritative_symbol: str,
    ) -> PendingEntry:
        setup_key = build_setup_key(
            symbol=authoritative_symbol,
            direction=request.decision,
            setup_timestamp=setup_timestamp,
            entry=request.entry,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
        )

        if setup_key in self._submitted_setup_keys:
            raise DuplicatePendingSetupError(
                "The structural setup was already submitted."
            )
        order_link_id = build_order_link_id(setup_key)
        if order_link_id in self._recovered_order_link_ids:
            raise DuplicatePendingSetupError(
                "The recovered pending order was already submitted."
            )
        if self.get_open_position() is not None:
            raise PendingEntryConflictError(
                "An open position blocks pending entry submission."
            )
        if self.has_pending_entry():
            raise PendingEntryConflictError(
                "An active pending entry blocks another submission."
            )

        self._submitted_setup_keys.add(setup_key)
        self._broker.submit_entry(
            request,
            order_link_id=order_link_id,
            setup_key=setup_key,
            signal_timestamp=signal_timestamp,
        )

        pending = self._broker.get_pending_entry()
        if pending is None or pending.order_link_id != order_link_id:
            raise PendingEntrySubmissionError(
                "Broker acknowledgement has no matching pending entry."
            )
        return pending

    def has_pending_entry(self) -> bool:
        return self._broker.get_pending_entry() is not None

    def get_pending_entry(self) -> PendingEntry | None:
        return self._broker.get_pending_entry()

    def get_entry_order(
        self,
        order_link_id: str,
    ) -> EntryOrderSnapshot | None:
        return self._broker.get_entry_order(order_link_id)

    def cancel_pending_entry(self) -> None:
        pending = self.get_pending_entry()
        if pending is None:
            return
        self._broker.cancel_entry(pending.order_link_id)

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
