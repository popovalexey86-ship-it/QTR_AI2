from dataclasses import dataclass
from datetime import datetime

from infrastructure.container import Container


@dataclass(frozen=True, slots=True)
class BybitTestnetPreflightReport:
    connectivity_ok: bool
    private_api_ok: bool
    symbol: str
    interval: str
    latest_completed_candle_timestamp: datetime | None
    completed_candle_count: int
    open_position_count: int
    owned_active_order_count: int
    foreign_active_order_count: int
    durable_state_present: bool
    ready: bool
    blocking_reason: str | None

    def summary(self) -> str:
        return "\n".join(
            (
                f"Testnet connectivity: {'OK' if self.connectivity_ok else 'FAILED'}",
                f"Authenticated private API: {'OK' if self.private_api_ok else 'FAILED'}",
                f"Symbol / interval: {self.symbol} / {self.interval}",
                "Latest completed candle: "
                + (
                    self.latest_completed_candle_timestamp.isoformat()
                    if self.latest_completed_candle_timestamp is not None
                    else "N/A"
                ),
                f"Completed candle count: {self.completed_candle_count}",
                f"Open position count: {self.open_position_count}",
                f"QTR-owned active order count: {self.owned_active_order_count}",
                f"Foreign/manual active order count: {self.foreign_active_order_count}",
                "Durable pending state: "
                + ("PRESENT" if self.durable_state_present else "ABSENT"),
                f"Result: {'READY' if self.ready else 'BLOCKED'}",
                f"Blocking reason: {self.blocking_reason or 'None'}",
            )
        )


def run_bybit_testnet_preflight(container: Container) -> BybitTestnetPreflightReport:
    config = container.config
    if config.bybit_testnet is not True:
        return _failed_report(container, "Bybit Testnet is required.")

    try:
        durable_state = container.pending_entry_store.load()
    except Exception:
        return _failed_report(container, "Durable pending state is invalid.")

    try:
        market_data = container.collector.collect_completed()
    except Exception:
        return _failed_report(
            container,
            "Completed candle connectivity check failed.",
            durable_state_present=durable_state is not None,
        )

    try:
        positions = container.broker.get_positions()
        owned_count, foreign_count = container.broker.inspect_active_order_counts()
    except Exception:
        return BybitTestnetPreflightReport(
            connectivity_ok=True,
            private_api_ok=False,
            symbol=config.trade_symbol,
            interval=config.trade_interval,
            latest_completed_candle_timestamp=market_data.last.timestamp,
            completed_candle_count=market_data.count,
            open_position_count=0,
            owned_active_order_count=0,
            foreign_active_order_count=0,
            durable_state_present=durable_state is not None,
            ready=False,
            blocking_reason="Authenticated private API check failed.",
        )

    reasons: list[str] = []
    if positions:
        reasons.append("Open position exists.")
    if owned_count:
        reasons.append("QTR-owned active order exists.")
    if foreign_count:
        reasons.append("Foreign or manual active order exists.")
    if durable_state is not None:
        reasons.append("Durable pending state exists.")
    return BybitTestnetPreflightReport(
        connectivity_ok=True,
        private_api_ok=True,
        symbol=config.trade_symbol,
        interval=config.trade_interval,
        latest_completed_candle_timestamp=market_data.last.timestamp,
        completed_candle_count=market_data.count,
        open_position_count=len(positions),
        owned_active_order_count=owned_count,
        foreign_active_order_count=foreign_count,
        durable_state_present=durable_state is not None,
        ready=not reasons,
        blocking_reason=" ".join(reasons) or None,
    )


def _failed_report(
    container: Container,
    reason: str,
    *,
    durable_state_present: bool = False,
) -> BybitTestnetPreflightReport:
    return BybitTestnetPreflightReport(
        connectivity_ok=False,
        private_api_ok=False,
        symbol=container.config.trade_symbol,
        interval=container.config.trade_interval,
        latest_completed_candle_timestamp=None,
        completed_candle_count=0,
        open_position_count=0,
        owned_active_order_count=0,
        foreign_active_order_count=0,
        durable_state_present=durable_state_present,
        ready=False,
        blocking_reason=reason,
    )
