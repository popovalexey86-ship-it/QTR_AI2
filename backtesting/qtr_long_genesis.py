import argparse
from datetime import UTC, date, datetime, time
from pathlib import Path

from backtesting.historical_data import (
    HistoricalCandleCache,
    HistoricalRequest,
    load_historical_data,
)
from backtesting.qtr_long_backtest import create_qtr_long_backtest_runner
from backtesting.qtr_long_diagnostics import write_qtr_long_diagnostics_csv
from backtesting.snapshots import iter_market_data_snapshots
from infrastructure.bybit.bybit_historical_client import BybitHistoricalClient
from strategies.qtr_long.strategy import QTRLongStrategy


def _utc_date(value: str) -> datetime:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from error
    return datetime.combine(parsed, time.min, tzinfo=UTC)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run QTR Long Genesis backtest with deterministic diagnostics.",
    )
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="15")
    parser.add_argument("--start", type=_utc_date, required=True)
    parser.add_argument("--end", type=_utc_date, required=True)
    parser.add_argument("--minimum-score", type=int, default=80)
    parser.add_argument("--risk-reward", type=float, default=2.0)
    parser.add_argument("--volume", type=float, default=1.0)
    parser.add_argument("--history-window", type=int, default=500)
    parser.add_argument("--cache-root", type=Path, default=Path(".cache/bybit"))
    parser.add_argument(
        "--diagnostics-csv",
        type=Path,
        default=Path("artifacts/qtr_long_genesis_diagnostics.csv"),
    )
    parser.add_argument("--refresh", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    symbol = args.symbol.strip().upper()

    request = HistoricalRequest(
        category="linear",
        symbol=symbol,
        interval=args.interval,
        start=args.start,
        end=args.end,
    )
    historical = load_historical_data(
        client=BybitHistoricalClient(),
        cache=HistoricalCandleCache(args.cache_root),
        request=request,
        refresh=args.refresh,
    )

    runner = create_qtr_long_backtest_runner(
        symbol=symbol,
        volume=args.volume,
        minimum_score=args.minimum_score,
        risk_reward=args.risk_reward,
    )
    snapshots = iter_market_data_snapshots(
        historical.candles,
        symbol=symbol,
        interval=args.interval,
        history_window=args.history_window,
    )
    result = runner.run(snapshots)

    strategy = runner.strategy
    if not isinstance(strategy, QTRLongStrategy):
        raise RuntimeError("Genesis diagnostics require QTRLongStrategy")

    diagnostics_path = write_qtr_long_diagnostics_csv(
        args.diagnostics_csv,
        signals=strategy.accepted_signals,
        trades=result.completed_trades,
    )

    print("QTR LONG GENESIS BACKTEST v0.2")
    print(f"Period: {args.start.date()} -> {args.end.date()}")
    print(f"Interval: {args.interval}m")
    print(f"Historical source: {historical.source}")
    print(f"Historical candles: {len(historical.candles)}")
    print(f"Minimum score: {args.minimum_score}")
    print(f"Risk/reward: {args.risk_reward:.2f}")
    print(f"Fixed volume: {args.volume:.8f}")
    print(result.summary())
    print(f"Diagnostics CSV: {diagnostics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
