import csv
from collections.abc import Sequence
from pathlib import Path

from core.decision import Decision
from core.trade import Trade
from strategies.qtr_long.diagnostics import LongSignalDiagnostic


class LongDiagnosticsError(RuntimeError):
    """Raised when signal and trade diagnostics cannot be reconciled safely."""


def write_qtr_long_diagnostics_csv(
    path: Path,
    *,
    signals: Sequence[LongSignalDiagnostic],
    trades: Sequence[Trade],
) -> Path:
    """Write one row per completed QTR Long trade with its signal context.

    Genesis v0.2 currently pairs accepted signals and completed trades by
    chronological order. This is valid for the deterministic single-position
    backtest only when every accepted signal becomes one completed trade.
    Mismatches are rejected instead of silently producing misleading output.
    """

    if len(signals) != len(trades):
        raise LongDiagnosticsError(
            "Cannot reconcile QTR Long diagnostics: "
            f"accepted_signals={len(signals)} completed_trades={len(trades)}"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "ticket",
        "symbol",
        "decision",
        "signal_timestamp",
        "opened_at",
        "closed_at",
        "hold_minutes",
        "setup_type",
        "score_total",
        "score_grade",
        "score_structure",
        "score_liquidity",
        "score_order_block",
        "score_fvg",
        "score_momentum",
        "score_volume",
        "score_location",
        "sweep_timestamp",
        "sweep_price",
        "sweep_extreme",
        "sweep_reclaim_close",
        "order_block_timestamp",
        "order_block_status",
        "order_block_low",
        "order_block_high",
        "order_block_midpoint",
        "planned_entry",
        "actual_entry",
        "stop_loss",
        "exit",
        "volume",
        "pnl",
        "fees",
        "result_r",
        "outcome",
    ]

    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for signal, trade in zip(signals, trades, strict=True):
            if trade.decision != Decision.BUY:
                raise LongDiagnosticsError(
                    f"QTR Long invariant violated by trade {trade.ticket}: "
                    f"decision={trade.decision.value}"
                )

            planned_risk_per_unit = signal.entry - signal.stop_loss
            actual_risk_amount = planned_risk_per_unit * trade.volume
            result_r = (
                trade.pnl / actual_risk_amount
                if actual_risk_amount > 0
                else 0.0
            )
            hold_minutes = (trade.closed_at - trade.opened_at).total_seconds() / 60.0

            writer.writerow(
                {
                    "ticket": trade.ticket,
                    "symbol": trade.symbol,
                    "decision": trade.decision.value,
                    "signal_timestamp": signal.signal_timestamp.isoformat(),
                    "opened_at": trade.opened_at.isoformat(),
                    "closed_at": trade.closed_at.isoformat(),
                    "hold_minutes": f"{hold_minutes:.2f}",
                    "setup_type": signal.setup_type,
                    "score_total": signal.score_total,
                    "score_grade": signal.score_grade,
                    "score_structure": signal.score_structure,
                    "score_liquidity": signal.score_liquidity,
                    "score_order_block": signal.score_order_block,
                    "score_fvg": signal.score_fvg,
                    "score_momentum": signal.score_momentum,
                    "score_volume": signal.score_volume,
                    "score_location": signal.score_location,
                    "sweep_timestamp": signal.sweep_timestamp.isoformat(),
                    "sweep_price": signal.sweep_price,
                    "sweep_extreme": signal.sweep_extreme,
                    "sweep_reclaim_close": signal.sweep_reclaim_close,
                    "order_block_timestamp": signal.order_block_timestamp.isoformat(),
                    "order_block_status": signal.order_block_status,
                    "order_block_low": signal.order_block_low,
                    "order_block_high": signal.order_block_high,
                    "order_block_midpoint": signal.order_block_midpoint,
                    "planned_entry": signal.entry,
                    "actual_entry": trade.entry,
                    "stop_loss": signal.stop_loss,
                    "exit": trade.exit,
                    "volume": trade.volume,
                    "pnl": trade.pnl,
                    "fees": trade.fees,
                    "result_r": f"{result_r:.6f}",
                    "outcome": "WIN" if trade.pnl > 0 else "LOSS",
                }
            )

    return path
