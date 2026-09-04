import argparse
from datetime import UTC, datetime
from pathlib import Path

from backtesting.historical_data import (
    HistoricalCandleCache,
    HistoricalRequest,
    load_historical_data,
)
from backtesting.qtr_long_backtest import run_qtr_long_backtest
from infrastructure.bybit.bybit_historical_client import BybitHistoricalClient


def _utc_date(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from error
    return parsed.replace(tzinfo=UTC)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the first fixed-volume QTR Long Genesis backtest.",
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

    result = run_qtr_long_backtest(
        candles=historical.candles,
        symbol=symbol,
        interval=args.interval,
        history_window=args.history_window,
        volume=args.volume,
        minimum_score=args.minimum_score,
        risk_reward=args.risk_reward,
    )

    print("QTR LONG GENESIS BACKTEST v0.1")
    print(f"Period: {args.start.date()} -> {args.end.date()}")
    print(f"Interval: {args.interval}m")
    print(f"Historical source: {historical.source}")
    print(f"Historical candles: {len(historical.candles)}")
    print(f"Minimum score: {args.minimum_score}")
    print(f"Risk/reward: {args.risk_reward:.2f}")
    print(f"Fixed volume: {args.volume:.8f}")
    print(result.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
