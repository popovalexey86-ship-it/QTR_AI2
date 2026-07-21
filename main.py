import argparse
import time

from config.bootstrap import create_trading_engine
from core.logger import logger
from engine.trading_engine import TradingEngine
from infrastructure.container import Container
from infrastructure.telegram_notifier import TelegramNotifier


def build_trading_engine() -> tuple[Container, TradingEngine]:
    """Build application dependencies without making a Bybit API call."""
    container = Container()
    return container, create_trading_engine(container)


def run_trading_cycle(container: Container, engine: TradingEngine) -> None:
    """Run the live polling loop when explicitly requested."""
    last_timestamp = None

    logger.info("Trading cycle started.")

    while True:
        try:
            market_data = container.collector.collect()

            if market_data.last.timestamp != last_timestamp:
                last_timestamp = market_data.last.timestamp
                engine.process(market_data)
                logger.info("Waiting for new candle...")

            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Trading cycle stopped.")
            return
        except Exception as exc:
            logger.exception(f"Trading loop error: {exc}")
            time.sleep(10)


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