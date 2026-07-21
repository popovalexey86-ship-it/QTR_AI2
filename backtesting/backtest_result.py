from dataclasses import dataclass

from core.pending_entry import PendingEntry
from core.trade import Trade


@dataclass(frozen=True, slots=True)
class BacktestResult:
    symbol: str
    candles_processed: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    gross_profit: float
    gross_loss: float
    net_pnl: float
    has_open_position: bool
    completed_trades: tuple[Trade, ...]
    rejected_orders: int = 0
    has_pending_entry: bool = False
    final_pending_entry: PendingEntry | None = None
    submitted_entries: int = 0
    filled_entries: int = 0
    expired_entries: int = 0

    def summary(self) -> str:
        status = "OPEN" if self.has_open_position else "FLAT"
        pending_status = (
            "NONE"
            if self.final_pending_entry is None
            else f"ACTIVE ({self.final_pending_entry.status.name})"
        )
        return "\n".join(
            (
                f"Backtest summary: {self.symbol}",
                f"Candles processed: {self.candles_processed}",
                f"Completed trades: {self.total_trades}",
                f"Wins / losses: {self.winning_trades} / {self.losing_trades}",
                f"Win rate: {self.win_rate * 100:.2f}%",
                f"Gross profit: {self.gross_profit:.8f}",
                f"Gross loss: {self.gross_loss:.8f}",
                f"Net PnL: {self.net_pnl:.8f}",
                f"Pending entries submitted: {self.submitted_entries}",
                f"Pending entries filled: {self.filled_entries}",
                f"Pending entries expired: {self.expired_entries}",
                f"Final position: {status}",
                f"Final pending entry: {pending_status}",
            )
        )
