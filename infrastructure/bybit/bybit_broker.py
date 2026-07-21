from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime
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
from core.position import Position
from core.trade import Trade
from core.trade_request import TradeRequest
from infrastructure.bybit.bybit_client import BybitClient
from infrastructure.bybit.bybit_entry_order_mapper import BybitEntryOrderMapper
from infrastructure.bybit.bybit_entry_order_snapshot_mapper import (
    BybitEntryOrderSnapshotMapper,
)
from infrastructure.bybit.bybit_order_mapper import BybitOrderMapper
from infrastructure.bybit.bybit_position_mapper import BybitPositionMapper
from infrastructure.bybit.bybit_trade_mapper import BybitTradeMapper


class BybitTestnetRequiredError(BrokerError):
    """Raised when pending entry submission is attempted outside Testnet."""


class BybitPendingEntryError(BrokerError):
    """Raised when the Bybit pending-entry lifecycle fails closed."""


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
        self._pending_entry: PendingEntry | None = None
        self._entry_orders: dict[str, PendingEntry] = {}
        self._cancel_requested_order_ids: set[str] = set()

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
        return EntryOrderAcknowledgement(
            order_link_id=order_link_id,
            exchange_order_id=exchange_order_id,
        )

    def get_entry_order(
        self,
        order_link_id: str,
    ) -> EntryOrderSnapshot | None:
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
            or order_link_id in self._cancel_requested_order_ids
            or active.status == PendingEntryStatus.CANCEL_REQUESTED
        ):
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

    def get_pending_entry(self) -> PendingEntry | None:
        return self._pending_entry

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

        if _is_stale_snapshot(active.status, snapshot.status):
            return _snapshot_from_pending(active)

        if (
            active.status == PendingEntryStatus.CANCEL_REQUESTED
            and snapshot.status == PendingEntryStatus.PARTIALLY_FILLED
        ):
            updated = replace(
                active,
                filled_volume=snapshot.filled_volume,
                average_fill_price=snapshot.average_fill_price,
                exchange_order_id=snapshot.exchange_order_id,
            )
        elif active.status == snapshot.status:
            updated = replace(
                active,
                filled_volume=snapshot.filled_volume,
                average_fill_price=snapshot.average_fill_price,
                exchange_order_id=snapshot.exchange_order_id,
            )
        else:
            try:
                validate_pending_entry_transition(active.status, snapshot.status)
            except InvalidPendingEntryTransition:
                raise BybitPendingEntryError(
                    "Bybit returned an invalid pending-entry state transition."
                ) from None
            updated = replace(
                active,
                status=snapshot.status,
                filled_volume=snapshot.filled_volume,
                average_fill_price=snapshot.average_fill_price,
                exchange_order_id=snapshot.exchange_order_id,
            )

        self._entry_orders[active.order_link_id] = updated
        self._pending_entry = updated

        if updated.status in _TERMINAL_ENTRY_STATUSES:
            self._pending_entry = None
            return snapshot

        if snapshot.status == PendingEntryStatus.PARTIALLY_FILLED:
            self.cancel_entry(active.order_link_id)
        return snapshot

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


_TERMINAL_ENTRY_STATUSES = frozenset(
    {
        PendingEntryStatus.FILLED,
        PendingEntryStatus.CANCELLED,
        PendingEntryStatus.REJECTED,
        PendingEntryStatus.EXPIRED,
    }
)
