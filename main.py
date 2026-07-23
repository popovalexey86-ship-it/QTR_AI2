import argparse
import time
from collections.abc import Callable
from datetime import UTC, datetime

from config.bootstrap import create_notifier, create_trading_engine
from core.exceptions import TemporaryExchangeError, TemporaryTransportError
from core.logger import logger
from core.notification import NotificationError, NotificationPort
from engine.trading_engine import TradingEngine
from infrastructure.container import Container
from infrastructure.telegram_notifier import TelegramNotifier
from infrastructure.config import Config


class LiveTestnetRequiredError(RuntimeError):
    """Raised when the MVP live loop is requested outside Bybit Testnet."""


class LiveConfigurationError(RuntimeError):
    """Raised when live Testnet configuration is incomplete or unsafe."""


_RUNTIME_ALERT_INTERVAL_SECONDS = 300.0
_TEMPORARY_RUNTIME_ERRORS = (
    TemporaryTransportError,
    TemporaryExchangeError,
)


class RuntimeBackoff:
    """Bounded backoff for consecutive temporary runtime failures."""

    def __init__(self) -> None:
        self._consecutive_failures = 0

    def next_delay(self) -> float:
        delay = min(5.0 * (2 ** self._consecutive_failures), 60.0)
        self._consecutive_failures += 1
        return delay

    def reset(self) -> None:
        self._consecutive_failures = 0


class RuntimeFailureAlertDeduplicator:
    """Throttle identical successful runtime-failure notifications."""

    def __init__(
        self,
        interval_seconds: float = _RUNTIME_ALERT_INTERVAL_SECONDS,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._interval_seconds = interval_seconds
        self._clock = clock or time.monotonic
        self._last_notified_at: dict[str, float] = {}

    def should_notify(self, failure_key: str) -> bool:
        last_notified_at = self._last_notified_at.get(failure_key)
        if last_notified_at is None:
            return True
        return self._clock() - last_notified_at >= self._interval_seconds

    def record_notification(self, failure_key: str) -> None:
        self._last_notified_at[failure_key] = self._clock()


def build_trading_engine() -> tuple[Container, TradingEngine]:
    """Build application dependencies without making a Bybit API call."""
    container = Container()
    return container, create_trading_engine(container)


def validate_live_configuration(config: Config) -> None:
    if config.bybit_testnet is not True:
        raise LiveConfigurationError("Bybit Testnet must be enabled.")
    if not config.bybit_api_key.strip() or not config.bybit_api_secret.strip():
        raise LiveConfigurationError(
            "Bybit API credentials are required for Testnet live mode."
        )
    try:
        config.bybit_pending_entry_state_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
    except OSError:
        raise LiveConfigurationError(
            "Pending-state parent directory cannot be prepared."
        ) from None


def check_live_configuration() -> None:
    config = Config.load()
    validate_live_configuration(config)
    container = Container(config)
    create_trading_engine(container)
    print("Mode: Bybit Testnet")
    print("Category: linear")
    print(f"Symbol: {config.trade_symbol}")
    print(f"Interval: {config.trade_interval}")
    print(f"Volume: {config.trade_volume}")
    print(f"TTL: {config.pending_entry_ttl_candles}")
    print(f"Pending-state path: {config.bybit_pending_entry_state_path}")
    print(f"Telegram: {'enabled' if config.telegram_enabled else 'disabled'}")
    print("Configuration valid")


def testnet_preflight() -> None:
    from infrastructure.bybit.bybit_preflight import run_bybit_testnet_preflight

    config = Config.load()
    validate_live_configuration(config)
    container = Container(config)
    report = run_bybit_testnet_preflight(container)
    print(report.summary())


def _notify_runtime_event(event: str, callback: Callable[[], None]) -> bool:
    try:
        callback()
    except NotificationError:
        logger.error("Runtime notification failed. Event=%s", event)
        return False
    return True


def _notify_runtime_failure(
    notifier: NotificationPort,
    deduplicator: RuntimeFailureAlertDeduplicator,
    error_message: str,
) -> None:
    if not deduplicator.should_notify(error_message):
        return
    if _notify_runtime_event(
        "failed",
        lambda: notifier.runtime_failed(error_message),
    ):
        deduplicator.record_notification(error_message)


def run_trading_cycle(
    container: Container,
    engine: TradingEngine,
    notifier: NotificationPort | None = None,
) -> None:
    """Run the live polling loop when explicitly requested."""
    if container.config.bybit_testnet is not True:
        raise LiveTestnetRequiredError(
            "Live trading is restricted to Bybit Testnet."
        )
    validate_live_configuration(container.config)

    if notifier is None:
        notifier = create_notifier(container.config)

    failure_alerts = RuntimeFailureAlertDeduplicator()
    temporary_backoff = RuntimeBackoff()

    while True:
        try:
            engine.recover_runtime_state()
            temporary_backoff.reset()
            break
        except _TEMPORARY_RUNTIME_ERRORS as error:
            error_message = (
                "Runtime recovery temporary error: "
                f"{type(error).__name__}"
            )
            logger.warning(error_message)
            _notify_runtime_failure(
                notifier,
                failure_alerts,
                error_message,
            )
            time.sleep(temporary_backoff.next_delay())
        except Exception as error:
            error_message = f"Runtime recovery failed: {type(error).__name__}"
            logger.error(error_message)
            _notify_runtime_failure(
                notifier,
                failure_alerts,
                error_message,
            )
            return

    successful_analysis_timestamp: datetime | None = None
    logger.info("Trading cycle started.")
    _notify_runtime_event("started", notifier.runtime_started)
    try:
        while True:
            try:
                engine.poll_runtime_state()
                market_data = container.collector.collect_completed()
                completed_timestamps = tuple(
                    candle.timestamp for candle in market_data.candles
                )
                latest_timestamp = market_data.last.timestamp

                if successful_analysis_timestamp is None:
                    engine.age_pending_entry(
                        completed_timestamps,
                        ttl_candles=container.config.pending_entry_ttl_candles,
                    )
                    successful_analysis_timestamp = latest_timestamp
                    logger.info("Waiting for new candle...")
                elif latest_timestamp < successful_analysis_timestamp:
                    raise RuntimeError(
                        "Completed candle timestamp regressed."
                    )
                elif latest_timestamp > successful_analysis_timestamp:
                    engine.age_pending_entry(
                        completed_timestamps,
                        ttl_candles=container.config.pending_entry_ttl_candles,
                    )
                    engine.process(market_data)
                    successful_analysis_timestamp = latest_timestamp
                    logger.info("Waiting for new candle...")

                temporary_backoff.reset()
                time.sleep(5)
            except _TEMPORARY_RUNTIME_ERRORS as error:
                error_message = (
                    "Trading loop temporary error: "
                    f"{type(error).__name__}"
                )
                logger.warning(error_message)
                _notify_runtime_failure(
                    notifier,
                    failure_alerts,
                    error_message,
                )
                time.sleep(temporary_backoff.next_delay())
            except Exception as error:
                temporary_backoff.reset()
                error_message = f"Trading loop error: {type(error).__name__}"
                logger.error(error_message)
                _notify_runtime_failure(
                    notifier,
                    failure_alerts,
                    error_message,
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
    check_live_config: bool = False,
    testnet_preflight_mode: bool = False,
) -> None:
    selected_modes = sum(
        bool(value)
        for value in (
            run_loop,
            test_telegram,
            backtest_sample,
            backtest_bybit,
            check_live_config,
            testnet_preflight_mode,
        )
    )
    if selected_modes > 1:
        raise ValueError("CLI modes are mutually exclusive.")

    if check_live_config:
        check_live_configuration()
        return

    if testnet_preflight_mode:
        testnet_preflight()
        return

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
    mode_group = parser.add_mutually_exclusive_group()

    mode_group.add_argument(
        "--run-live",
        action="store_true",
        help="Start the live trading cycle after assembling the application.",
    )

    mode_group.add_argument(
        "--test-telegram",
        action="store_true",
        help="Send a Telegram test notification and exit.",
    )

    mode_group.add_argument(
        "--backtest-sample",
        action="store_true",
        help="Run the deterministic in-memory backtest sample and exit.",
    )

    mode_group.add_argument(
        "--backtest-bybit",
        action="store_true",
        help="Run a cached backtest using public Bybit historical candles.",
    )
    mode_group.add_argument(
        "--check-live-config",
        action="store_true",
        help="Validate live Testnet configuration without network requests.",
    )
    mode_group.add_argument(
        "--testnet-preflight",
        action="store_true",
        help="Run read-only Bybit Testnet readiness checks.",
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
        check_live_config=arguments.check_live_config,
        testnet_preflight_mode=arguments.testnet_preflight,
    )
