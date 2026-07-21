from dataclasses import replace
from datetime import datetime

from core.broker import Broker
from core.candle import Candle
from core.decision import Decision
from core.entry_order import EntryOrderAcknowledgement, EntryOrderSnapshot
from core.pending_entry import (
    PendingEntry,
    PendingEntryStatus,
    validate_pending_entry_transition,
)
from core.position import Position
from core.trade import Trade
from core.trade_request import TradeRequest


class SimulatedOrderRejected(ValueError):
    """Raised when fixed protective levels are invalid for a market fill."""


class SimulatedBroker(Broker):
    """Deterministic single-symbol market and resting-limit simulator.

    ``open_position`` preserves the legacy candle-close market-fill behavior.
    ``submit_entry`` creates a resting limit entry that can fill only on a
    post-signal candle. Both paths use zero fees by default and deterministic
    stop-first exit handling.
    """

    def __init__(
        self,
        symbol: str,
        fee: float = 0.0,
        pending_entry_ttl_candles: int = 4,
    ) -> None:
        if not symbol:
            raise ValueError("Backtest symbol cannot be empty.")
        if fee < 0:
            raise ValueError("Simulated fee cannot be negative.")
        if (
            isinstance(pending_entry_ttl_candles, bool)
            or not isinstance(pending_entry_ttl_candles, int)
            or pending_entry_ttl_candles <= 0
        ):
            raise ValueError(
                "Pending entry TTL must be a positive integer number of candles."
            )

        self._symbol = symbol
        self._fee = fee
        self._pending_entry_ttl_candles = pending_entry_ttl_candles
        self._position: Position | None = None
        self._last_closed_trade: Trade | None = None
        self._current_candle: Candle | None = None
        self._next_ticket = 1
        self._next_entry_order_id = 1
        self._pending_entry: PendingEntry | None = None
        self._entry_orders: dict[str, PendingEntry] = {}
        self._last_pending_candle_timestamp: datetime | None = None

    def update_market(self, candle: Candle) -> None:
        self._current_candle = candle
        position_before_update = self._position
        pending_fill = self._process_pending_entry(candle)

        if pending_fill is not None:
            position, marketable_at_open = pending_fill
            self._evaluate_pending_fill_exit(
                position,
                candle,
                marketable_at_open=marketable_at_open,
            )
            return

        if position_before_update is None:
            return
        if candle.timestamp <= position_before_update.opened_at:
            return

        self._evaluate_position_exit(position_before_update, candle)

    def submit_entry(
        self,
        request: TradeRequest,
        *,
        order_link_id: str,
        setup_key: str,
        signal_timestamp: datetime,
    ) -> EntryOrderAcknowledgement:
        """Submit one deterministic resting limit entry without filling it."""

        if self._position is not None:
            raise RuntimeError(
                "Cannot submit a simulated entry while a position is open."
            )

        active = self._pending_entry
        if active is not None:
            if active.order_link_id != order_link_id:
                raise RuntimeError("A simulated pending entry is already active.")
            if (
                active.request != request
                or active.setup_key != setup_key
                or active.signal_timestamp != signal_timestamp
            ):
                raise ValueError(
                    "An active order link ID cannot be reused for another entry."
                )
            return EntryOrderAcknowledgement(
                order_link_id=active.order_link_id,
                exchange_order_id=active.exchange_order_id,
            )

        if order_link_id in self._entry_orders:
            raise ValueError("A terminal order link ID cannot be reused.")

        exchange_order_id = f"SIM-ENTRY-{self._next_entry_order_id:06d}"
        self._next_entry_order_id += 1
        pending = PendingEntry(
            order_link_id=order_link_id,
            setup_key=setup_key,
            request=request,
            signal_timestamp=signal_timestamp,
            exchange_order_id=exchange_order_id,
        )
        self._entry_orders[order_link_id] = pending

        try:
            self._validate_protective_levels(request, request.entry)
        except SimulatedOrderRejected:
            rejected = self._transition_entry(
                pending,
                PendingEntryStatus.REJECTED,
            )
            self._entry_orders[order_link_id] = rejected
            raise

        self._pending_entry = pending
        self._last_pending_candle_timestamp = None
        return EntryOrderAcknowledgement(
            order_link_id=order_link_id,
            exchange_order_id=exchange_order_id,
        )

    def get_entry_order(
        self,
        order_link_id: str,
    ) -> EntryOrderSnapshot | None:
        entry = self._entry_orders.get(order_link_id)
        if entry is None:
            return None

        return EntryOrderSnapshot(
            order_link_id=entry.order_link_id,
            exchange_order_id=entry.exchange_order_id,
            status=entry.status,
            requested_volume=entry.request.volume,
            filled_volume=entry.filled_volume,
            average_fill_price=entry.average_fill_price,
        )

    def cancel_entry(self, order_link_id: str) -> None:
        entry = self._entry_orders.get(order_link_id)
        if entry is None or entry.status in _TERMINAL_ENTRY_STATUSES:
            return

        if entry.status == PendingEntryStatus.SUBMITTED:
            cancelled = self._transition_entry(
                entry,
                PendingEntryStatus.CANCELLED,
            )
        else:
            cancel_requested = self._transition_entry(
                entry,
                PendingEntryStatus.CANCEL_REQUESTED,
            )
            cancelled = self._transition_entry(
                cancel_requested,
                PendingEntryStatus.CANCELLED,
            )

        self._store_terminal_entry(cancelled)

    def get_pending_entry(self) -> PendingEntry | None:
        return self._pending_entry

    @property
    def submitted_entry_count(self) -> int:
        return len(self._entry_orders)

    @property
    def filled_entry_count(self) -> int:
        return sum(
            entry.status == PendingEntryStatus.FILLED
            for entry in self._entry_orders.values()
        )

    @property
    def expired_entry_count(self) -> int:
        return sum(
            entry.status == PendingEntryStatus.EXPIRED
            for entry in self._entry_orders.values()
        )

    @property
    def rejected_entry_count(self) -> int:
        return sum(
            entry.status == PendingEntryStatus.REJECTED
            for entry in self._entry_orders.values()
        )

    def _process_pending_entry(
        self,
        candle: Candle,
    ) -> tuple[Position, bool] | None:
        entry = self._pending_entry
        if entry is None or candle.timestamp <= entry.signal_timestamp:
            return None
        if self._last_pending_candle_timestamp == candle.timestamp:
            return None

        self._last_pending_candle_timestamp = candle.timestamp
        if entry.status == PendingEntryStatus.SUBMITTED:
            entry = self._transition_entry(
                entry,
                PendingEntryStatus.WORKING,
            )

        entry = replace(
            entry,
            completed_candles_active=entry.completed_candles_active + 1,
        )
        self._pending_entry = entry
        self._entry_orders[entry.order_link_id] = entry

        marketable_at_open = self._is_marketable_at_open(entry.request, candle)
        touched_intrabar = (
            candle.low <= entry.request.entry <= candle.high
        )
        if marketable_at_open or touched_intrabar:
            position = self._fill_pending_entry(entry, candle)
            return position, marketable_at_open

        if (
            entry.completed_candles_active
            >= self._pending_entry_ttl_candles
        ):
            cancel_requested = self._transition_entry(
                entry,
                PendingEntryStatus.CANCEL_REQUESTED,
            )
            expired = self._transition_entry(
                cancel_requested,
                PendingEntryStatus.EXPIRED,
            )
            self._store_terminal_entry(expired)

        return None

    def _fill_pending_entry(
        self,
        entry: PendingEntry,
        candle: Candle,
    ) -> Position:
        request = entry.request
        ticket = f"SIM-{self._next_ticket:06d}"
        self._next_ticket += 1
        position = Position(
            ticket=ticket,
            symbol=self._symbol,
            decision=request.decision,
            entry=request.entry,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            volume=request.volume,
            opened_at=candle.timestamp,
        )
        filled = self._transition_entry(
            entry,
            PendingEntryStatus.FILLED,
            filled_volume=request.volume,
            average_fill_price=request.entry,
        )
        self._position = position
        self._store_terminal_entry(filled)
        return position

    @staticmethod
    def _is_marketable_at_open(request: TradeRequest, candle: Candle) -> bool:
        if request.decision == Decision.BUY:
            return candle.open <= request.entry
        if request.decision == Decision.SELL:
            return candle.open >= request.entry
        return False

    def _evaluate_pending_fill_exit(
        self,
        position: Position,
        candle: Candle,
        *,
        marketable_at_open: bool,
    ) -> None:
        stop_touched = self._stop_touched(position, candle)
        if stop_touched:
            self._close_at(position, position.stop_loss)
            return

        if marketable_at_open and self._take_profit_touched(position, candle):
            self._close_at(position, position.take_profit)

    def _evaluate_position_exit(
        self,
        position: Position,
        candle: Candle,
    ) -> None:
        exit_price: float | None = None
        if self._stop_touched(position, candle):
            exit_price = position.stop_loss
        elif self._take_profit_touched(position, candle):
            exit_price = position.take_profit

        if exit_price is not None:
            self._close_at(position, exit_price)

    @staticmethod
    def _stop_touched(position: Position, candle: Candle) -> bool:
        if position.decision == Decision.BUY:
            return candle.low <= position.stop_loss
        if position.decision == Decision.SELL:
            return candle.high >= position.stop_loss
        return False

    @staticmethod
    def _take_profit_touched(position: Position, candle: Candle) -> bool:
        if position.decision == Decision.BUY:
            return candle.high >= position.take_profit
        if position.decision == Decision.SELL:
            return candle.low <= position.take_profit
        return False

    def _transition_entry(
        self,
        entry: PendingEntry,
        target: PendingEntryStatus,
        *,
        filled_volume: float | None = None,
        average_fill_price: float | None = None,
    ) -> PendingEntry:
        validate_pending_entry_transition(entry.status, target)
        transitioned = replace(
            entry,
            status=target,
            filled_volume=(
                entry.filled_volume
                if filled_volume is None
                else filled_volume
            ),
            average_fill_price=(
                entry.average_fill_price
                if average_fill_price is None
                else average_fill_price
            ),
        )
        self._entry_orders[entry.order_link_id] = transitioned
        if (
            self._pending_entry is not None
            and self._pending_entry.order_link_id == entry.order_link_id
        ):
            self._pending_entry = transitioned
        return transitioned

    def _store_terminal_entry(self, entry: PendingEntry) -> None:
        self._entry_orders[entry.order_link_id] = entry
        if (
            self._pending_entry is not None
            and self._pending_entry.order_link_id == entry.order_link_id
        ):
            self._pending_entry = None
            self._last_pending_candle_timestamp = None

    def open_position(self, request: TradeRequest) -> Position:
        if self._position is not None:
            raise RuntimeError("A simulated position is already open.")
        if self._pending_entry is not None:
            raise RuntimeError(
                "Cannot open a simulated position while an entry is pending."
            )
        if self._current_candle is None:
            raise RuntimeError("Market data must be processed before opening.")

        fill_price = self._current_candle.close
        self._validate_protective_levels(request, fill_price)

        ticket = f"SIM-{self._next_ticket:06d}"
        self._next_ticket += 1
        self._position = Position(
            ticket=ticket,
            # The runner's validated single symbol is authoritative. The
            # current RiskManager keeps a live BTCUSDT default in TradeRequest.
            symbol=self._symbol,
            decision=request.decision,
            entry=fill_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            volume=request.volume,
            opened_at=self._current_candle.timestamp,
        )
        return self._position

    @staticmethod
    def _validate_protective_levels(
        request: TradeRequest,
        fill_price: float,
    ) -> None:
        valid = False
        if request.decision == Decision.BUY:
            valid = request.stop_loss < fill_price < request.take_profit
        elif request.decision == Decision.SELL:
            valid = request.take_profit < fill_price < request.stop_loss

        if not valid:
            raise SimulatedOrderRejected(
                "Protective levels are invalid for the simulated market fill."
            )

    def close_position(self, position: Position) -> None:
        if self._position is None or self._position.ticket != position.ticket:
            raise ValueError("The requested simulated position is not open.")
        if self._current_candle is None:
            raise RuntimeError("No market price is available for closing.")

        self._close_at(position, self._current_candle.close)

    def get_positions(self) -> list[Position]:
        return [] if self._position is None else [self._position]

    def get_open_position(self) -> Position | None:
        return self._position

    def get_last_closed_trade(self) -> Trade | None:
        return self._last_closed_trade

    def _close_at(self, position: Position, exit_price: float) -> None:
        if self._current_candle is None:
            raise RuntimeError("No market price is available for closing.")

        price_change = exit_price - position.entry
        if position.decision == Decision.SELL:
            price_change = -price_change

        self._last_closed_trade = Trade(
            ticket=position.ticket,
            symbol=position.symbol,
            decision=position.decision,
            entry=position.entry,
            exit=exit_price,
            volume=position.volume,
            pnl=price_change * position.volume - self._fee,
            fees=self._fee,
            opened_at=position.opened_at,
            closed_at=self._current_candle.timestamp,
        )
        self._position = None


_TERMINAL_ENTRY_STATUSES = frozenset(
    {
        PendingEntryStatus.FILLED,
        PendingEntryStatus.CANCELLED,
        PendingEntryStatus.REJECTED,
        PendingEntryStatus.EXPIRED,
    }
)
