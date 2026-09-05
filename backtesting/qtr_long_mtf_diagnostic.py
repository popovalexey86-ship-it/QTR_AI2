from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from backtesting.historical_data import HistoricalCandleCache
from backtesting.qtr_long_hierarchy_backtest import (
    QTRLongHierarchyBacktestConfig,
    run_qtr_long_hierarchy_backtest,
)
from backtesting.qtr_long_hierarchy_runner import QTRLongHierarchyBacktestResult
from backtesting.qtr_long_mtf_historical import (
    QTRLongHistoricalLoadRequest,
    load_qtr_long_historical_bundle,
)
from infrastructure.bybit.bybit_historical_client import BybitHistoricalClient
from strategies.qtr_long.hierarchy import LongHierarchyStage


_DEEP_STAGES = {
    LongHierarchyStage.DISPLACEMENT_5M,
    LongHierarchyStage.STRUCTURE_5M,
    LongHierarchyStage.ENTRY_5M,
    LongHierarchyStage.READY,
}


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("datetime must be timezone-aware UTC")
    parsed = parsed.astimezone(UTC)
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        raise argparse.ArgumentTypeError("datetime must use UTC")
    return parsed


def format_diagnostic_report(
    *,
    result: QTRLongHierarchyBacktestResult,
    data_start: datetime,
    evaluation_start: datetime,
    end: datetime,
) -> str:
    lines = [
        "QTR LONG vNext — MTF DIAGNOSTIC",
        f"Symbol: {result.symbol}",
        f"Data start: {data_start.isoformat()}",
        f"Evaluation start: {evaluation_start.isoformat()}",
        f"End: {end.isoformat()}",
        f"Snapshots processed: {result.snapshots_processed}",
        f"BUY_PLAN: {result.buy_plan_count}",
        f"SKIP: {result.skip_count}",
        "Stage counts:",
    ]
    for stage in LongHierarchyStage:
        lines.append(f"  {stage.value}: {result.stage_counts.get(stage, 0)}")

    if result.decision_times:
        deep_candidates = [
            (as_of, decision)
            for as_of, decision in zip(
                result.decision_times,
                result.decisions,
                strict=True,
            )
            if decision.stage in _DEEP_STAGES
        ]
        lines.append("Deep candidates:")
        if not deep_candidates:
            lines.append("  none")
        else:
            for index, (as_of, decision) in enumerate(deep_candidates, start=1):
                lines.append(
                    f"  #{index} as_of={as_of.isoformat()} "
                    f"stage={decision.stage.value} "
                    f"decision={decision.decision.value} "
                    f"reason={decision.reason}"
                )

    if result.buy_plans:
        lines.append("BUY plans:")
        for index, plan in enumerate(result.buy_plans, start=1):
            lines.append(
                "  "
                f"#{index} source={plan.source.value} "
                f"entry={plan.entry:.8f} stop={plan.stop_loss:.8f} "
                f"zone=[{plan.zone_low:.8f}, {plan.zone_high:.8f}]"
            )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a real BTCUSDT-style QTR Long vNext MTF diagnostic."
    )
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--data-start", required=True, type=_parse_utc)
    parser.add_argument("--evaluation-start", required=True, type=_parse_utc)
    parser.add_argument("--end", required=True, type=_parse_utc)
    parser.add_argument("--history-window", type=int, default=500)
    parser.add_argument("--cache-root", type=Path, default=Path(".cache/bybit"))
    parser.add_argument("--refresh", action="store_true")
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
    result = run_qtr_long_hierarchy_backtest(
        bundle=bundle,
        config=QTRLongHierarchyBacktestConfig(
            symbol=args.symbol,
            history_window=args.history_window,
            evaluation_start=args.evaluation_start,
        ),
    )
    print(
        format_diagnostic_report(
            result=result,
            data_start=args.data_start,
            evaluation_start=args.evaluation_start,
            end=args.end,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
