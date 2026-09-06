from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
from pathlib import Path

from backtesting.historical_data import HistoricalCandleCache
from backtesting.qtr_long_execution_backtest import (
    LongExecutionBacktestConfig,
    run_qtr_long_execution_backtest,
)
from backtesting.qtr_long_forensic import build_qtr_long_filled_forensics
from backtesting.qtr_long_hierarchy_backtest import (
    QTRLongHierarchyBacktestConfig,
    run_qtr_long_hierarchy_backtest,
)
from backtesting.qtr_long_mtf_historical import (
    QTRLongHistoricalLoadRequest,
    load_qtr_long_historical_bundle,
)
from infrastructure.bybit.bybit_historical_client import BybitHistoricalClient


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("datetime must be timezone-aware UTC")
    return parsed.astimezone(UTC)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export forensic rows for filled QTR Long Candidate B trades."
    )
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--data-start", required=True, type=_parse_utc)
    parser.add_argument("--evaluation-start", required=True, type=_parse_utc)
    parser.add_argument("--end", required=True, type=_parse_utc)
    parser.add_argument("--history-window", type=int, default=500)
    parser.add_argument("--cache-root", type=Path, default=Path(".cache/bybit"))
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--rr", type=float, default=2.0)
    parser.add_argument("--pending-ttl-candles", type=int, default=12)
    parser.add_argument("--risk-pct", type=float, default=0.005)
    parser.add_argument("--initial-equity", type=float, default=10_000.0)
    parser.add_argument("--output", type=Path, default=Path("qtr_long_candidate_b_forensic.csv"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.data_start < args.evaluation_start < args.end:
        raise SystemExit("Expected data-start < evaluation-start < end.")

    client = BybitHistoricalClient()
    cache = HistoricalCandleCache(args.cache_root)
    request = QTRLongHistoricalLoadRequest(
        category="linear",
        symbol=args.symbol,
        start=args.data_start,
        end=args.end,
    )
    bundle = load_qtr_long_historical_bundle(
        client=client,
        cache=cache,
        request=request,
        refresh=args.refresh,
    )
    hierarchy_result = run_qtr_long_hierarchy_backtest(
        bundle=bundle,
        config=QTRLongHierarchyBacktestConfig(
            symbol=args.symbol,
            history_window=args.history_window,
            evaluation_start=args.evaluation_start,
        ),
    )
    execution_result = run_qtr_long_execution_backtest(
        hierarchy_result=hierarchy_result,
        execution_candles=bundle.execution_5m.candles,
        config=LongExecutionBacktestConfig(
            rr=args.rr,
            pending_ttl_candles=args.pending_ttl_candles,
            risk_pct=args.risk_pct,
            initial_equity=args.initial_equity,
        ),
    )
    rows = build_qtr_long_filled_forensics(
        hierarchy_result=hierarchy_result,
        execution_result=execution_result,
    )

    fieldnames = [
        "plan_time",
        "outcome",
        "result_r",
        "entry_source",
        "entry",
        "stop_loss",
        "take_profit",
        "stop_distance_pct",
        "target_distance_pct",
        "fill_delay_minutes",
        "raid_to_displacement_candles",
        "displacement_to_plan_candles",
        "body_ratio",
        "range_expansion",
        "close_location",
        "execution_trend",
        "last_choch",
        "last_bos",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "plan_time": row.plan_time.isoformat(),
                    "outcome": row.outcome,
                    "result_r": f"{row.result_r:.2f}",
                    "entry_source": row.entry_source,
                    "entry": f"{row.entry:.8f}",
                    "stop_loss": f"{row.stop_loss:.8f}",
                    "take_profit": f"{row.take_profit:.8f}",
                    "stop_distance_pct": f"{row.stop_distance_pct:.6f}",
                    "target_distance_pct": f"{row.target_distance_pct:.6f}",
                    "fill_delay_minutes": f"{row.fill_delay_minutes:.2f}",
                    "raid_to_displacement_candles": row.raid_to_displacement_candles,
                    "displacement_to_plan_candles": row.displacement_to_plan_candles,
                    "body_ratio": row.body_ratio,
                    "range_expansion": row.range_expansion,
                    "close_location": row.close_location,
                    "execution_trend": row.execution_trend,
                    "last_choch": row.last_choch,
                    "last_bos": row.last_bos,
                }
            )

    print(f"Forensic rows: {len(rows)}")
    print(f"CSV: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
