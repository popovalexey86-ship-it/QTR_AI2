from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timedelta
import math
import time
from typing import Any

from core.broker import Broker
from core.entry_order import EntryOrderAcknowledgement, EntryOrderSnapshot
from core.exceptions import BrokerError, OrderRejectedError
from core.pending_entry import (
    InvalidPendingEntryTransition,
    PendingEntry,
    PendingEntryStatus,
    validate_pending_entry_transition,
)
from core.pending_entry_event import PendingEntryEvent, PendingEntryEventKind
from core.position import Position
from core.trade import Trade
from core.trade_request import TradeRequest
from infrastructure.bybit.bybit_client import BybitClient
from infrastructure.bybit.bybit_entry_order_mapper import BybitEntryOrderMapper
from infrastructure.bybit.bybit_entry_order_snapshot_mapper import (
    BybitEntryOrderSnapshotMapper,
    extract_order_items,
)
from infrastructure.bybit.bybit_order_mapper import BybitOrderMapper
from infrastructure.bybit.bybit_pending_entry_store import (
    SCHEMA_VERSION,
    BybitPendingEntryStore,
    BybitPendingEntryStoreError,
    PersistedBybitPendingEntry,
)
from infrastructure.bybit.bybit_position_mapper import BybitPositionMapper
from infrastructure.bybit.bybit_trade_mapper import BybitTradeMapper


class BybitTestnetRequiredError(BrokerError):
    """Raised when pending entry submission is attempted outside Testnet."""


class BybitPendingEntryError(BrokerError):
    """Raised when the Bybit pending-entry lifecycle fails closed."""


class BybitPendingEntryPersistenceError(BybitPendingEntryError):
    """Raised when local durable state cannot be updated safely."""


class BybitActiveOrderConflictError(BybitPendingEntryError):
    """Raised when active exchange-order ownership is ambiguous."""


class BybitPendingEntryRecoveryError(BybitPendingEntryError):
    """Raised when startup pending-entry recovery cannot proceed safely."""


class BybitBroker(Broker):
    def __init__(
        self,
        client: BybitClient,
        category: str,
        symbol: str,
        order_mapper: BybitOrderMapper | None = None,
        position_mapper: BybitPositionMapper | None = None,
        entry_order_mapper: BybitEntryOrderMapper | None = None,
        entry_snapshot_mapper: BybitEntryOrderSnapshotMapper | None = None,
        pending_entry_store: BybitPendingEntryStore | None = None,
    ) -> None:
        self._client = client
        self._order_mapper = order_mapper or BybitOrderMapper()
        self._position_mapper = position_mapper or BybitPositionMapper()
        self._entry_order_mapper = entry_order_mapper or BybitEntryOrderMapper()
        self._entry_snapshot_mapper = (
            entry_snapshot_mapper or BybitEntryOrderSnapshotMapper()
        )
        self._category = category
        self._symbol = symbol
        self._pending_entry_store = pending_entry_store
        self._pending_entry: PendingEntry | None = None
        self._entry_orders: dict[str, PendingEntry] = {}
        self._cancel_requested_order_ids: set[str] = set()
        self._last_aged_candle_timestamp: datetime | None = None
        self._pending_entry_events: list[PendingEntryEvent] = []
        self._recovering = False
        self._recovery_event_order_ids: set[str] = set()
        self._submission_event_order_ids: set[str] = set()
        self._last_reconciled_terminal: tuple[
            PendingEntry,
            PendingEntryStatus,
            str | None,
        ] | None = None

    def submit_entry(
        self,
        request: TradeRequest,
        *,
        order_link_id: str,
        setup_key: str,
        signal_timestamp: datetime,
    ) -> EntryOrderAcknowledgement:
        if self._client.is_testnet is not True:
            raise BybitTestnetRequiredError(
                "Pending entries are restricted to Bybit Testnet."
            )

        active = self._pending_entry
        if active is not None:
            if active.order_link_id != order_link_id:
                raise BybitPendingEntryError(
                    "Another pending entry is already active."
                )
            if (
                active.request != request
                or active.setup_key != setup_key
                or active.signal_timestamp != signal_timestamp
            ):
                raise BybitPendingEntryError(
                    "The active order link ID has conflicting content."
                )
            self._persist_pending_entry(active)
            if order_link_id not in self._submission_event_order_ids:
                self._queue_pending_event(
                    active,
                    kind=PendingEntryEventKind.SUBMITTED,
                    previous_status=None,
                )
                self._submission_event_order_ids.add(order_link_id)
            return EntryOrderAcknowledgement(
                order_link_id=active.order_link_id,
                exchange_order_id=active.exchange_order_id,
            )

        if order_link_id in self._entry_orders:
            raise BybitPendingEntryError(
                "A known terminal order link ID cannot be reused."
            )
        try:
            open_position = self.get_open_position()
        except Exception:
            raise BybitPendingEntryError(
                "Bybit open-position safety check failed."
            ) from None
        if open_position is not None:
            raise BybitPendingEntryError(
                "An open position blocks pending entry submission."
            )
        self._ensure_submission_has_no_active_order_conflict()

        mapped_request = self._entry_order_mapper.to_order_request(
            request,
            symbol=self._symbol,
            order_link_id=order_link_id,
        )
        try:
            response = self._client.place_order(
                category=self._category,
                **mapped_request,
            )
        except Exception:
            raise BybitPendingEntryError(
                "Bybit pending entry submission request failed."
            ) from None
        _require_mapping_response(
            response,
            operation="pending entry submission",
        )
        result = _require_success_result(
            response,
            operation="pending entry submission",
        )
        exchange_order_id = _require_result_id(result, "orderId")
        _validate_optional_result_id(
            result,
            field_name="orderLinkId",
            expected=order_link_id,
        )

        pending = PendingEntry(
            order_link_id=order_link_id,
            setup_key=setup_key,
            request=request,
            signal_timestamp=signal_timestamp,
            status=PendingEntryStatus.SUBMITTED,
            exchange_order_id=exchange_order_id,
        )
        self._pending_entry = pending
        self._entry_orders[order_link_id] = pending
        self._persist_pending_entry(pending)
        self._queue_pending_event(
            pending,
            kind=PendingEntryEventKind.SUBMITTED,
            previous_status=None,
        )
        self._submission_event_order_ids.add(order_link_id)
        return EntryOrderAcknowledgement(
            order_link_id=order_link_id,
            exchange_order_id=exchange_order_id,
        )

    def get_entry_order(
        self,
        order_link_id: str,
    ) -> EntryOrderSnapshot | None:
        snapshot, _ = self._query_entry_order(order_link_id)

        active = self._pending_entry
        if snapshot is None:
            if active is not None and active.order_link_id == order_link_id:
                raise BybitPendingEntryError(
                    "The active pending entry is missing from Bybit order queries."
                )
            return None

        if active is None or active.order_link_id != order_link_id:
            return snapshot
        return self._reconcile_active_entry(active, snapshot)

    def _query_entry_order(
        self,
        order_link_id: str,
    ) -> tuple[EntryOrderSnapshot | None, bool]:
        try:
            realtime_response = self._client.get_open_orders(
                category=self._category,
                symbol=self._symbol,
                order_link_id=order_link_id,
            )
        except Exception:
            raise BybitPendingEntryError(
                "Bybit realtime entry-order query failed."
            ) from None
        _require_mapping_response(
            realtime_response,
            operation="realtime entry-order query",
        )
        snapshot = self._entry_snapshot_mapper.from_response(
            realtime_response,
            expected_order_link_id=order_link_id,
        )
        if snapshot is not None:
            return snapshot, True

        if snapshot is None:
            try:
                history_response = self._client.get_order_history(
                    category=self._category,
                    symbol=self._symbol,
                    order_link_id=order_link_id,
                )
            except Exception:
                raise BybitPendingEntryError(
                    "Bybit historical entry-order query failed."
                ) from None
            _require_mapping_response(
                history_response,
                operation="historical entry-order query",
            )
            snapshot = self._entry_snapshot_mapper.from_response(
                history_response,
                expected_order_link_id=order_link_id,
            )
        return snapshot, False

    def cancel_entry(self, order_link_id: str) -> None:
        active = self._pending_entry
        known = self._entry_orders.get(order_link_id)
        if active is None:
            if known is None or known.status in _TERMINAL_ENTRY_STATUSES:
                return
            raise BybitPendingEntryError(
                "Known pending state is inconsistent with the active slot."
            )
        if active.order_link_id != order_link_id:
            raise BybitPendingEntryError(
                "Cancellation order link ID does not match the active entry."
            )
        if (
            active.status in _TERMINAL_ENTRY_STATUSES
        ):
            return
        if (
            order_link_id in self._cancel_requested_order_ids
            or active.status == PendingEntryStatus.CANCEL_REQUESTED
        ):
            self._persist_pending_entry(active)
            return

        try:
            response = self._client.cancel_order(
                category=self._category,
                symbol=self._symbol,
                order_link_id=order_link_id,
                order_id=active.exchange_order_id,
            )
        except Exception:
            raise BybitPendingEntryError(
                "Bybit pending entry cancellation request failed."
            ) from None
        _require_mapping_response(
            response,
            operation="pending entry cancellation",
        )
        result = _require_success_result(
            response,
            operation="pending entry cancellation",
        )
        _validate_optional_result_id(
            result,
            field_name="orderLinkId",
            expected=order_link_id,
        )
        if active.exchange_order_id is not None:
            _validate_optional_result_id(
                result,
                field_name="orderId",
                expected=active.exchange_order_id,
            )

        try:
            validate_pending_entry_transition(
                active.status,
                PendingEntryStatus.CANCEL_REQUESTED,
            )
        except InvalidPendingEntryTransition:
            raise BybitPendingEntryError(
                "Pending entry cannot enter cancellation state."
            ) from None

        cancel_requested = replace(
            active,
            status=PendingEntryStatus.CANCEL_REQUESTED,
        )
        self._pending_entry = cancel_requested
        self._entry_orders[order_link_id] = cancel_requested
        self._cancel_requested_order_ids.add(order_link_id)
        self._persist_pending_entry(cancel_requested)
        self._queue_pending_event(
            cancel_requested,
            kind=PendingEntryEventKind.STATUS_CHANGED,
            previous_status=active.status,
        )

    def recover_pending_entry(self) -> PendingEntry | None:
        self._recovering = True
        self._last_reconciled_terminal = None
        try:
            recovered = self._recover_pending_entry()
        finally:
            self._recovering = False

        if recovered is not None:
            if recovered.order_link_id not in self._recovery_event_order_ids:
                self._queue_pending_event(
                    recovered,
                    kind=PendingEntryEventKind.RECOVERED,
                    previous_status=None,
                )
                self._recovery_event_order_ids.add(recovered.order_link_id)
        elif self._last_reconciled_terminal is not None:
            terminal, previous_status, rejection_reason = (
                self._last_reconciled_terminal
            )
            if terminal.order_link_id not in self._recovery_event_order_ids:
                self._queue_pending_event(
                    terminal,
                    kind=PendingEntryEventKind.TERMINAL,
                    previous_status=previous_status,
                    rejection_reason=rejection_reason,
                )
                self._recovery_event_order_ids.add(terminal.order_link_id)
        return recovered

    def _recover_pending_entry(self) -> PendingEntry | None:
        if self._pending_entry_store is None:
            raise BybitPendingEntryRecoveryError(
                "Pending-entry recovery requires durable storage."
            )

        try:
            persisted = self._pending_entry_store.load()
        except BybitPendingEntryStoreError:
            raise BybitPendingEntryRecoveryError(
                "Durable pending-entry state could not be loaded."
            ) from None

        active_orders = self._list_active_exchange_orders()
        owned_orders, foreign_orders = _classify_active_orders(active_orders)
        if foreign_orders:
            raise BybitActiveOrderConflictError(
                "A foreign or manual active order blocks QTR recovery."
            )
        if len(owned_orders) > 1:
            raise BybitActiveOrderConflictError(
                "Multiple QTR-owned active orders block recovery."
            )

        if persisted is None:
            if owned_orders:
                raise BybitPendingEntryRecoveryError(
                    "An orphaned QTR-owned active order requires manual review."
                )
            self._pending_entry = None
            return None

        restored = persisted.pending_entry
        self._validate_recovery_state(restored)
        if owned_orders:
            owned_item = owned_orders[0]
            owned_order_link_id = _order_link_id(owned_item)
            if owned_order_link_id != restored.order_link_id:
                raise BybitPendingEntryRecoveryError(
                    "Durable state does not match the active QTR order."
                )
            self._validate_exchange_order_scope(owned_item)
            if self._safe_get_open_position_for_recovery() is not None:
                raise BybitPendingEntryRecoveryError(
                    "An open position and active entry order are ambiguous."
                )
            try:
                snapshot = self._entry_snapshot_mapper.from_item(
                    owned_item,
                    expected_order_link_id=restored.order_link_id,
                )
            except BrokerError:
                raise BybitPendingEntryRecoveryError(
                    "The active QTR order snapshot is malformed."
                ) from None
            self._restore_pending_entry(persisted)
            self._reconcile_recovered_entry(restored, snapshot)
            self._resume_expiry_cancellation()
            return self._pending_entry

        self._restore_pending_entry(persisted)
        try:
            queried_snapshot, found_realtime = self._query_entry_order(
                restored.order_link_id
            )
        except BrokerError:
            raise BybitPendingEntryRecoveryError(
                "Pending-entry lookup during recovery failed."
            ) from None
        if queried_snapshot is None:
            raise BybitPendingEntryRecoveryError(
                "Durable pending entry is missing from Bybit order queries."
            )
        self._reconcile_recovered_entry(restored, queried_snapshot)
        if queried_snapshot.status in _TERMINAL_ENTRY_STATUSES:
            return None
        if not found_realtime:
            raise BybitPendingEntryRecoveryError(
                "Historical state does not prove an active pending entry."
            )
        self._resume_expiry_cancellation()
        return self._pending_entry

    def refresh_pending_entry(self) -> PendingEntry | None:
        active = self._pending_entry
        if active is None:
            return None
        self.get_entry_order(active.order_link_id)
        return self._pending_entry

    def age_pending_entry(
        self,
        completed_candle_timestamps: tuple[datetime, ...],
        *,
        ttl_candles: int,
    ) -> PendingEntry | None:
        _validate_ttl(ttl_candles)
        normalized_timestamps = _normalize_completed_timestamps(
            completed_candle_timestamps
        )
        active = self._pending_entry
        if active is None:
            return None
        if active.status in _TERMINAL_ENTRY_STATUSES:
            return active

        refreshed = self.refresh_pending_entry()
        if refreshed is None:
            return None
        if refreshed.status == PendingEntryStatus.CANCEL_REQUESTED:
            return refreshed
        if refreshed.expiry_requested:
            self._resume_expiry_cancellation()
            return self._pending_entry

        last_aged = self._last_aged_candle_timestamp
        if (
            last_aged is not None
            and normalized_timestamps
            and normalized_timestamps[-1] < last_aged
        ):
            raise BybitPendingEntryError(
                "Completed candle timestamps regressed during pending-entry aging."
            )
        eligible = tuple(
            timestamp
            for timestamp in normalized_timestamps
            if timestamp > refreshed.signal_timestamp
            and (last_aged is None or timestamp > last_aged)
        )
        if not eligible:
            return refreshed

        updated_count = refreshed.completed_candles_active + len(eligible)
        expiry_requested = updated_count >= ttl_candles
        updated = replace(
            refreshed,
            completed_candles_active=updated_count,
            expiry_requested=expiry_requested,
        )
        self._store_aged_pending_entry(
            previous=refreshed,
            updated=updated,
            last_aged_timestamp=eligible[-1],
        )
        if expiry_requested:
            self.cancel_entry(updated.order_link_id)
        return self._pending_entry

    def _reconcile_recovered_entry(
        self,
        restored: PendingEntry,
        snapshot: EntryOrderSnapshot,
    ) -> None:
        try:
            self._reconcile_active_entry(restored, snapshot)
        except BybitPendingEntryPersistenceError:
            raise
        except BrokerError:
            raise BybitPendingEntryRecoveryError(
                "Pending-entry state could not be reconciled during recovery."
            ) from None

    def _resume_expiry_cancellation(self) -> None:
        active = self._pending_entry
        if (
            active is None
            or not active.expiry_requested
            or active.status == PendingEntryStatus.CANCEL_REQUESTED
            or active.status in _TERMINAL_ENTRY_STATUSES
        ):
            return
        self.cancel_entry(active.order_link_id)

    def _store_aged_pending_entry(
        self,
        *,
        previous: PendingEntry,
        updated: PendingEntry,
        last_aged_timestamp: datetime,
    ) -> None:
        previous_last_aged = self._last_aged_candle_timestamp
        self._pending_entry = updated
        self._entry_orders[updated.order_link_id] = updated
        self._last_aged_candle_timestamp = last_aged_timestamp
        try:
            self._persist_pending_entry(updated)
        except BybitPendingEntryPersistenceError:
            self._pending_entry = previous
            self._entry_orders[previous.order_link_id] = previous
            self._last_aged_candle_timestamp = previous_last_aged
            raise

    def get_pending_entry(self) -> PendingEntry | None:
        return self._pending_entry

    def drain_pending_entry_events(self) -> tuple[PendingEntryEvent, ...]:
        events = tuple(self._pending_entry_events)
        self._pending_entry_events.clear()
        return events

    def inspect_active_order_counts(self) -> tuple[int, int]:
        active_orders = self._list_active_exchange_orders()
        owned, foreign = _classify_active_orders(active_orders)
        return len(owned), len(foreign)

    def _queue_pending_event(
        self,
        entry: PendingEntry,
        *,
        kind: PendingEntryEventKind,
        previous_status: PendingEntryStatus | None,
        rejection_reason: str | None = None,
    ) -> None:
        if self._recovering:
            return
        self._pending_entry_events.append(
            PendingEntryEvent(
                kind=kind,
                order_link_id=entry.order_link_id,
                exchange_order_id=entry.exchange_order_id,
                symbol=self._symbol,
                decision=entry.request.decision,
                status=entry.status,
                previous_status=previous_status,
                entry=entry.request.entry,
                requested_volume=entry.request.volume,
                filled_volume=entry.filled_volume,
                average_fill_price=entry.average_fill_price,
                rejection_reason=rejection_reason,
                signal_timestamp=entry.signal_timestamp,
            )
        )

    def _restore_pending_entry(
        self,
        persisted: PersistedBybitPendingEntry,
    ) -> None:
        restored = persisted.pending_entry
        self._pending_entry = restored
        self._entry_orders[restored.order_link_id] = restored
        self._last_aged_candle_timestamp = persisted.last_aged_candle_timestamp
        if restored.status == PendingEntryStatus.CANCEL_REQUESTED:
            self._cancel_requested_order_ids.add(restored.order_link_id)

    def _validate_recovery_state(self, entry: PendingEntry) -> None:
        if not entry.order_link_id.startswith("QTR-"):
            raise BybitPendingEntryRecoveryError(
                "Durable state is not owned by QTR."
            )
        if entry.request.symbol.strip().upper() != self._symbol.strip().upper():
            raise BybitPendingEntryRecoveryError(
                "Durable pending-entry symbol does not match the broker."
            )

    def _validate_exchange_order_scope(
        self,
        item: Mapping[str, Any],
    ) -> None:
        item_symbol = item.get("symbol")
        if (
            item_symbol is not None
            and (
                not isinstance(item_symbol, str)
                or item_symbol.strip().upper() != self._symbol.strip().upper()
            )
        ):
            raise BybitPendingEntryRecoveryError(
                "The active order symbol does not match the broker."
            )
        item_category = item.get("category")
        if (
            item_category is not None
            and (
                not isinstance(item_category, str)
                or item_category.strip() != self._category
            )
        ):
            raise BybitPendingEntryRecoveryError(
                "The active order category does not match the broker."
            )

    def _safe_get_open_position_for_recovery(self) -> Position | None:
        try:
            return self.get_open_position()
        except Exception:
            raise BybitPendingEntryRecoveryError(
                "Open-position recovery check failed."
            ) from None

    def _list_active_exchange_orders(
        self,
    ) -> tuple[Mapping[str, Any], ...]:
        try:
            response = self._client.list_open_orders(
                category=self._category,
                symbol=self._symbol,
            )
        except Exception:
            raise BybitActiveOrderConflictError(
                "Bybit active-order listing failed."
            ) from None
        try:
            _require_mapping_response(
                response,
                operation="active-order listing",
            )
            return extract_order_items(response)
        except BrokerError:
            raise BybitActiveOrderConflictError(
                "Bybit active-order listing is malformed."
            ) from None

    def _ensure_submission_has_no_active_order_conflict(self) -> None:
        active_orders = self._list_active_exchange_orders()
        owned_orders, foreign_orders = _classify_active_orders(active_orders)
        if foreign_orders:
            raise BybitActiveOrderConflictError(
                "A foreign or manual active order blocks submission."
            )
        if owned_orders:
            raise BybitActiveOrderConflictError(
                "An orphaned QTR-owned active order blocks submission."
            )

    def _persist_pending_entry(self, entry: PendingEntry) -> None:
        if self._pending_entry_store is None:
            return
        state = PersistedBybitPendingEntry(
            schema_version=SCHEMA_VERSION,
            pending_entry=entry,
            last_aged_candle_timestamp=self._last_aged_candle_timestamp,
        )
        try:
            self._pending_entry_store.save(state)
        except BybitPendingEntryStoreError:
            raise BybitPendingEntryPersistenceError(
                "Durable pending-entry state could not be saved."
            ) from None

    def _clear_persisted_pending_entry(self) -> None:
        if self._pending_entry_store is None:
            return
        try:
            self._pending_entry_store.clear()
        except BybitPendingEntryStoreError:
            raise BybitPendingEntryPersistenceError(
                "Durable pending-entry state could not be cleared."
            ) from None

    def _reconcile_active_entry(
        self,
        active: PendingEntry,
        snapshot: EntryOrderSnapshot,
    ) -> EntryOrderSnapshot:
        if (
            active.exchange_order_id is not None
            and snapshot.exchange_order_id != active.exchange_order_id
        ):
            raise BybitPendingEntryError(
                "Bybit returned a conflicting exchange order ID."
            )
        if not math.isclose(
            snapshot.requested_volume,
            active.request.volume,
            rel_tol=1e-12,
            abs_tol=0.0,
        ):
            raise BybitPendingEntryError(
                "Bybit returned a conflicting requested quantity."
            )
        if snapshot.filled_volume < active.filled_volume:
            raise BybitPendingEntryError(
                "Bybit returned a regressing filled quantity."
            )

        effective_snapshot = snapshot
        transition_active = active
        if (
            snapshot.status == PendingEntryStatus.CANCELLED
            and active.expiry_requested
            and active.filled_volume == 0
            and snapshot.filled_volume == 0
        ):
            effective_snapshot = replace(
                snapshot,
                status=PendingEntryStatus.EXPIRED,
            )
            if active.status != PendingEntryStatus.CANCEL_REQUESTED:
                try:
                    validate_pending_entry_transition(
                        active.status,
                        PendingEntryStatus.CANCEL_REQUESTED,
                    )
                except InvalidPendingEntryTransition:
                    raise BybitPendingEntryError(
                        "Expiry cancellation confirmation is inconsistent."
                    ) from None
                transition_active = replace(
                    active,
                    status=PendingEntryStatus.CANCEL_REQUESTED,
                )

        if _is_stale_snapshot(active.status, effective_snapshot.status):
            self._persist_pending_entry(active)
            return _snapshot_from_pending(active)

        if (
            active.status == PendingEntryStatus.CANCEL_REQUESTED
            and effective_snapshot.status == PendingEntryStatus.PARTIALLY_FILLED
        ):
            updated = replace(
                active,
                filled_volume=effective_snapshot.filled_volume,
                average_fill_price=effective_snapshot.average_fill_price,
                exchange_order_id=effective_snapshot.exchange_order_id,
            )
        elif active.status == effective_snapshot.status:
            updated = replace(
                active,
                filled_volume=effective_snapshot.filled_volume,
                average_fill_price=effective_snapshot.average_fill_price,
                exchange_order_id=effective_snapshot.exchange_order_id,
            )
        else:
            try:
                validate_pending_entry_transition(
                    transition_active.status,
                    effective_snapshot.status,
                )
            except InvalidPendingEntryTransition:
                raise BybitPendingEntryError(
                    "Bybit returned an invalid pending-entry state transition."
                ) from None
            updated = replace(
                active,
                status=effective_snapshot.status,
                filled_volume=effective_snapshot.filled_volume,
                average_fill_price=effective_snapshot.average_fill_price,
                exchange_order_id=effective_snapshot.exchange_order_id,
            )

        self._entry_orders[active.order_link_id] = updated
        self._pending_entry = updated

        if updated.status in _TERMINAL_ENTRY_STATUSES:
            terminal_previous_status = transition_active.status
            self._pending_entry = None
            try:
                self._clear_persisted_pending_entry()
            except BybitPendingEntryPersistenceError:
                self._pending_entry = updated
                raise
            self._last_reconciled_terminal = (
                updated,
                terminal_previous_status,
                effective_snapshot.rejection_reason,
            )
            self._queue_pending_event(
                updated,
                kind=PendingEntryEventKind.TERMINAL,
                previous_status=terminal_previous_status,
                rejection_reason=effective_snapshot.rejection_reason,
            )
            return effective_snapshot

        self._persist_pending_entry(updated)
        if updated != active:
            self._queue_pending_event(
                updated,
                kind=PendingEntryEventKind.STATUS_CHANGED,
                previous_status=active.status,
            )
        if effective_snapshot.status == PendingEntryStatus.PARTIALLY_FILLED:
            self.cancel_entry(active.order_link_id)
        return effective_snapshot

    def open_position(self, request: TradeRequest) -> Position:
        order = self._order_mapper.to_order_request(request)
        response = self._client.place_order(
            category=self._category,
            **order,
        )
        if response.get("retCode", 0) != 0:
            raise OrderRejectedError(
                f'Bybit error {response["retCode"]}: {response["retMsg"]}'
            )
        if "result" not in response:
            raise BrokerError("Invalid Bybit response.")

        try:
            return self._position_mapper.from_order_response(
                response=response,
                request=request,
            )
        except AttributeError:
            pass

        for _ in range(5):
            positions = self.get_positions()
            if positions:
                return positions[0]
            time.sleep(0.2)
        raise BrokerError("Position was not found after order execution.")

    def close_position(self, position: Position) -> None:
        order = self._order_mapper.to_close_order_request(position)
        response = self._client.place_order(
            category=self._category,
            **order,
        )
        if response.get("retCode", 0) != 0:
            raise OrderRejectedError(
                f'Bybit error {response["retCode"]}: {response["retMsg"]}'
            )

    def get_positions(self) -> list[Position]:
        response = self._client.get_positions(
            category=self._category,
            symbol=self._symbol,
        )
        if response.get("retCode", 0) != 0:
            raise BrokerError(
                f'Bybit error {response["retCode"]}: {response["retMsg"]}'
            )

        positions: list[Position] = []
        for item in response.get("result", {}).get("list", []):
            if float(item.get("size", 0)) == 0:
                continue
            positions.append(self._position_mapper.from_position(item))
        return positions

    def get_open_position(self) -> Position | None:
        positions = self.get_positions()
        if not positions:
            return None
        return positions[0]

    def get_last_closed_trade(self) -> Trade | None:
        response = self._client.get_closed_pnl(
            category=self._category,
            symbol=self._symbol,
            limit=1,
        )
        if response.get("retCode", 0) != 0:
            raise BrokerError(
                f'Bybit error {response["retCode"]}: {response["retMsg"]}'
            )
        trades = response.get("result", {}).get("list", [])
        if not trades:
            return None
        return BybitTradeMapper.from_closed_pnl(trades[0])


def _require_success_result(
    response: Mapping[str, Any],
    *,
    operation: str,
) -> Mapping[str, Any]:
    ret_code = response.get("retCode")
    if (
        isinstance(ret_code, bool)
        or not isinstance(ret_code, int)
        or ret_code != 0
    ):
        raise BybitPendingEntryError(f"Bybit {operation} failed.")
    result = response.get("result")
    if not isinstance(result, Mapping):
        raise BybitPendingEntryError(
            f"Bybit {operation} returned a malformed result."
        )
    return result


def _require_mapping_response(
    response: object,
    *,
    operation: str,
) -> None:
    if not isinstance(response, Mapping):
        raise BybitPendingEntryError(
            f"Bybit {operation} returned a malformed response."
        )


def _require_result_id(result: Mapping[str, Any], field_name: str) -> str:
    value = result.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise BybitPendingEntryError(
            "Bybit acknowledgement contains a missing order identifier."
        )
    return value.strip()


def _validate_optional_result_id(
    result: Mapping[str, Any],
    *,
    field_name: str,
    expected: str,
) -> None:
    if field_name not in result:
        return
    value = result.get(field_name)
    if not isinstance(value, str) or not value.strip() or value.strip() != expected:
        raise BybitPendingEntryError(
            "Bybit acknowledgement contains a conflicting order identifier."
        )


def _snapshot_from_pending(entry: PendingEntry) -> EntryOrderSnapshot:
    return EntryOrderSnapshot(
        order_link_id=entry.order_link_id,
        exchange_order_id=entry.exchange_order_id,
        status=entry.status,
        requested_volume=entry.request.volume,
        filled_volume=entry.filled_volume,
        average_fill_price=entry.average_fill_price,
    )


def _is_stale_snapshot(
    local_status: PendingEntryStatus,
    snapshot_status: PendingEntryStatus,
) -> bool:
    stale_by_local_status = {
        PendingEntryStatus.WORKING: {PendingEntryStatus.SUBMITTED},
        PendingEntryStatus.PARTIALLY_FILLED: {
            PendingEntryStatus.SUBMITTED,
            PendingEntryStatus.WORKING,
        },
        PendingEntryStatus.CANCEL_REQUESTED: {
            PendingEntryStatus.SUBMITTED,
            PendingEntryStatus.WORKING,
        },
    }
    return snapshot_status in stale_by_local_status.get(local_status, set())


def _classify_active_orders(
    orders: tuple[Mapping[str, Any], ...],
) -> tuple[tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    owned: list[Mapping[str, Any]] = []
    foreign: list[Mapping[str, Any]] = []
    for item in orders:
        order_link_id = item.get("orderLinkId")
        if isinstance(order_link_id, str) and order_link_id.startswith("QTR-"):
            owned.append(item)
        else:
            foreign.append(item)
    return tuple(owned), tuple(foreign)


def _order_link_id(item: Mapping[str, Any]) -> str:
    value = item.get("orderLinkId")
    if not isinstance(value, str) or not value:
        raise BybitActiveOrderConflictError(
            "An active QTR order has an invalid order link ID."
        )
    return value


def _validate_ttl(ttl_candles: int) -> None:
    if (
        isinstance(ttl_candles, bool)
        or not isinstance(ttl_candles, int)
        or ttl_candles <= 0
    ):
        raise BybitPendingEntryError(
            "Pending-entry TTL must be a positive integer."
        )


def _normalize_completed_timestamps(
    timestamps: tuple[datetime, ...],
) -> tuple[datetime, ...]:
    for timestamp in timestamps:
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise BybitPendingEntryError(
                "Completed candle timestamps must be timezone-aware UTC."
            )
        if timestamp.utcoffset() != timedelta(0):
            raise BybitPendingEntryError(
                "Completed candle timestamps must use UTC."
            )
    return tuple(sorted(set(timestamps)))


_TERMINAL_ENTRY_STATUSES = frozenset(
    {
        PendingEntryStatus.FILLED,
        PendingEntryStatus.CANCELLED,
        PendingEntryStatus.REJECTED,
        PendingEntryStatus.EXPIRED,
    }
)
