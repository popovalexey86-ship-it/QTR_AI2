from dataclasses import dataclass

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

    def summary(self) -> str:
        status = "OPEN" if self.has_open_position else "FLAT"
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
                f"Final position: {status}",
            )
        )
