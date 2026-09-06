from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from backtesting.historical_data import HistoricalCandleCache
from backtesting.qtr_long_execution_backtest import (
    LongExecutionBacktestConfig,
    LongExecutionBacktestResult,
    run_qtr_long_execution_backtest,
)
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


def format_execution_report(
    *,
    result: LongExecutionBacktestResult,
    symbol: str,
    data_start: datetime,
    evaluation_start: datetime,
    end: datetime,
    config: LongExecutionBacktestConfig,
) -> str:
    pf = "inf" if result.profit_factor is None and result.wins else (
        "n/a" if result.profit_factor is None else f"{result.profit_factor:.4f}"
    )
    lines = [
        "QTR LONG Candidate B — EXECUTION BACKTEST",
        f"Symbol: {symbol}",
        f"Data start: {data_start.isoformat()}",
        f"Evaluation start: {evaluation_start.isoformat()}",
        f"End: {end.isoformat()}",
        f"RR: {config.rr:.2f}",
        f"Risk per closed trade: {config.risk_pct * 100:.2f}%",
        f"Pending TTL: {config.pending_ttl_candles} x 5m candles",
        f"Initial equity: {result.initial_equity:.2f}",
        f"Plans: {result.plans}",
        f"Filled: {result.filled}",
        f"Expired: {result.expired}",
        f"Open at data end: {result.open_count}",
        f"Wins: {result.wins}",
        f"Losses: {result.losses}",
        f"Win rate: {result.win_rate * 100:.2f}%",
        f"Net R: {result.net_r:.2f}",
        f"Expectancy: {result.expectancy_r:.4f} R/closed trade",
        f"Profit factor: {pf}",
        f"Max drawdown: {result.max_drawdown_pct * 100:.2f}%",
        f"Final equity: {result.final_equity:.2f}",
        "Assumptions: next-candle eligibility; SL-first on same-candle SL/TP; no fees/funding/slippage.",
        "Trades:",
    ]
    for index, trade in enumerate(result.trades, start=1):
        lines.append(
            f"  #{index} plan={trade.plan_time.isoformat()} "
            f"outcome={trade.outcome.value} entry={trade.entry:.8f} "
            f"sl={trade.stop_loss:.8f} tp={trade.take_profit:.8f} "
            f"fill={trade.fill_time.isoformat() if trade.fill_time else '-'} "
            f"exit={trade.exit_time.isoformat() if trade.exit_time else '-'} "
            f"R={trade.result_r:.2f}"
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run QTR Long Candidate B decision + execution backtest."
    )
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--data-start", required=True, type=_parse_utc)
    parser.add_argument("--evaluation-start", required=True, type=_parse_utc)
    parser.add_argument("--end", required=True, type=_parse_utc)
    parser.add_argument("--history-window", type=int, default=500)
    parser.add_argument("--rr", type=float, default=2.0)
    parser.add_argument("--pending-ttl-candles", type=int, default=12)
    parser.add_argument("--risk-pct", type=float, default=0.005)
    parser.add_argument("--initial-equity", type=float, default=10_000.0)
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
    hierarchy = run_qtr_long_hierarchy_backtest(
        bundle=bundle,
        config=QTRLongHierarchyBacktestConfig(
            symbol=args.symbol,
            history_window=args.history_window,
            evaluation_start=args.evaluation_start,
        ),
    )
    execution_config = LongExecutionBacktestConfig(
        rr=args.rr,
        pending_ttl_candles=args.pending_ttl_candles,
        risk_pct=args.risk_pct,
        initial_equity=args.initial_equity,
    )
    execution = run_qtr_long_execution_backtest(
        hierarchy_result=hierarchy,
        execution_candles=bundle.execution_5m.candles,
        config=execution_config,
    )
    print(
        format_execution_report(
            result=execution,
            symbol=args.symbol,
            data_start=args.data_start,
            evaluation_start=args.evaluation_start,
            end=args.end,
            config=execution_config,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
