from collections.abc import Iterator
from contextlib import contextmanager
import logging

from core.logger import logger


@contextmanager
def scoped_backtest_logging(*, verbose: bool = False) -> Iterator[None]:
    """Suppress per-candle INFO logs and always restore the logger level."""
    original_level = logger.level
    logger.setLevel(logging.DEBUG if verbose else logging.WARNING)
    try:
        yield
    finally:
        logger.setLevel(original_level)
