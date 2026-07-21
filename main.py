import argparse
import time
from collections.abc import Callable

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


def main(
    run_loop: bool = False,
    test_telegram: bool = False,
) -> None:
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

    arguments = parser.parse_args()

    main(
        run_loop=arguments.run_live,
        test_telegram=arguments.test_telegram,
    )
