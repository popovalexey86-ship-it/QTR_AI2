import argparse
import time
from collections.abc import Callable
from datetime import UTC, datetime

from config.bootstrap import create_notifier, create_trading_engine
from core.logger import logger
from core.notification import NotificationError, NotificationPort
from engine.trading_engine import TradingEngine
from infrastructure.container import Container
from infrastructure.telegram_notifier import TelegramNotifier


def build_trading_engine() -> tuple[Container, TradingEngine]:
    """Build application dependencies without making a Bybit API call."""
    container = Container()
    return container, create_trading_engine(container)


def _notify_runtime_event(event: str, callback: Callable[[], None]) -> None:
    try:
        callback()
    except NotificationError:
        logger.error("Runtime notification failed. Event=%s", event)


def run_trading_cycle(
    container: Container,
    engine: TradingEngine,
    notifier: NotificationPort | None = None,
) -> None:
    """Run the live polling loop when explicitly requested."""
    last_timestamp = None
    if notifier is None:
        notifier = create_notifier(container.config)

    logger.info("Trading cycle started.")

    try:
        _notify_runtime_event("started", notifier.runtime_started)

        while True:
            try:
                market_data = container.collector.collect()

                if market_data.last.timestamp != last_timestamp:
                    last_timestamp = market_data.last.timestamp
                    engine.process(market_data)
                    logger.info("Waiting for new candle...")

                time.sleep(5)
            except Exception as error:
                error_message = f"Trading loop error: {type(error).__name__}"
                logger.error(error_message)
                _notify_runtime_event(
                    "failed",
                    lambda: notifier.runtime_failed(error_message),
                )
                time.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Trading cycle stopped.")
        _notify_runtime_event("stopped", notifier.runtime_stopped)


def send_telegram_test(container: Container) -> None:
    """Send one Telegram test notification and exit."""
    notifier = TelegramNotifier(
        bot_token=container.config.telegram_bot_token or "",
        chat_id=container.config.telegram_chat_id or "",
    )
    notifier.test_connection()
    logger.info("Telegram test notification sent.")


def run_sample_backtest() -> None:
    """Run the deterministic in-memory sample without live dependencies."""
    from backtesting.bootstrap import create_sample_backtest_runner
    from backtesting.sample_data import create_sample_snapshots

    result = create_sample_backtest_runner().run(create_sample_snapshots())
    print(result.summary())


def parse_utc_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise argparse.ArgumentTypeError(
            "Timestamp must be a valid ISO-8601 UTC datetime."
        ) from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("Timestamp must be timezone-aware UTC.")
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        raise argparse.ArgumentTypeError("Timestamp must use UTC.")
    return parsed.astimezone(UTC)


def run_bybit_backtest(
    *,
    symbol: str,
    interval: str,
    start: datetime,
    end: datetime,
    refresh_cache: bool = False,
    history_window: int = 500,
    verbose: bool = False,
) -> None:
    """Download/cache public candles and run without live dependencies."""
    from backtesting.bootstrap import create_backtest_runner
    from backtesting.historical_data import (
        HistoricalCandleCache,
        HistoricalRequest,
        load_historical_data,
    )
    from backtesting.logging import scoped_backtest_logging
    from backtesting.snapshots import iter_market_data_snapshots
    from infrastructure.bybit.bybit_historical_client import BybitHistoricalClient

    if history_window <= 0:
        raise ValueError("History window must be greater than zero.")

    request = HistoricalRequest(
        category="linear",
        symbol=symbol,
        interval=interval,
        start=start,
        end=end,
    )
    historical = load_historical_data(
        client=BybitHistoricalClient(),
        cache=HistoricalCandleCache(),
        request=request,
        refresh=refresh_cache,
    )
    snapshots = iter_market_data_snapshots(
        historical.candles,
        symbol=symbol,
        interval=interval,
        history_window=history_window,
    )
    with scoped_backtest_logging(verbose=verbose):
        result = create_backtest_runner(symbol).run(snapshots)

    print(f"Source: {historical.source}")
    print("Category: linear")
    print(f"Symbol / interval: {symbol} / {interval}")
    print(f"Requested range: {start.isoformat()} -> {end.isoformat()}")
    print(f"Candles downloaded: {len(historical.candles)}")
    print(f"Candles processed: {result.candles_processed}")
    print(f"Rejected simulated orders: {result.rejected_orders}")
    print(f"Cache path: {historical.cache_path}")
    print(result.summary())


def main(
    run_loop: bool = False,
    test_telegram: bool = False,
    backtest_sample: bool = False,
    backtest_bybit: bool = False,
    symbol: str | None = None,
    interval: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    refresh_cache: bool = False,
    history_window: int = 500,
    verbose_backtest: bool = False,
) -> None:
    if backtest_sample:
        run_sample_backtest()
        return

    if backtest_bybit:
        if symbol is None or interval is None or start is None or end is None:
            raise ValueError(
                "Bybit backtest requires symbol, interval, start, and end."
            )
        run_bybit_backtest(
            symbol=symbol,
            interval=interval,
            start=start,
            end=end,
            refresh_cache=refresh_cache,
            history_window=history_window,
            verbose=verbose_backtest,
        )
        return

    container, engine = build_trading_engine()

    if test_telegram:
        send_telegram_test(container)
        return

    if not run_loop:
        logger.info("Trading engine assembled. Live cycle was not started.")
        return

    run_trading_cycle(container, engine)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--run-live",
        action="store_true",
        help="Start the live trading cycle after assembling the application.",
    )

    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="Send a Telegram test notification and exit.",
    )

    parser.add_argument(
        "--backtest-sample",
        action="store_true",
        help="Run the deterministic in-memory backtest sample and exit.",
    )

    parser.add_argument(
        "--backtest-bybit",
        action="store_true",
        help="Run a cached backtest using public Bybit historical candles.",
    )
    parser.add_argument("--symbol")
    parser.add_argument("--interval")
    parser.add_argument("--start", type=parse_utc_datetime)
    parser.add_argument("--end", type=parse_utc_datetime)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--history-window", type=int, default=500)
    parser.add_argument("--verbose-backtest", action="store_true")

    arguments = parser.parse_args()

    if arguments.backtest_bybit:
        missing = [
            name
            for name in ("symbol", "interval", "start", "end")
            if getattr(arguments, name) is None
        ]
        if missing:
            parser.error(
                "--backtest-bybit requires --symbol, --interval, --start, and --end"
            )

    main(
        run_loop=arguments.run_live,
        test_telegram=arguments.test_telegram,
        backtest_sample=arguments.backtest_sample,
        backtest_bybit=arguments.backtest_bybit,
        symbol=arguments.symbol,
        interval=arguments.interval,
        start=arguments.start,
        end=arguments.end,
        refresh_cache=arguments.refresh_cache,
        history_window=arguments.history_window,
        verbose_backtest=arguments.verbose_backtest,
    )
