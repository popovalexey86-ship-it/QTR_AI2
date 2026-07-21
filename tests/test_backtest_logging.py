import logging

import pytest

from backtesting.logging import scoped_backtest_logging
from core.logger import logger


def test_backtest_logging_level_is_restored_after_success():
    original_level = logger.level

    with scoped_backtest_logging():
        assert logger.level == logging.WARNING

    assert logger.level == original_level


def test_backtest_logging_level_is_restored_after_error():
    original_level = logger.level

    with pytest.raises(RuntimeError):
        with scoped_backtest_logging():
            raise RuntimeError("failure")

    assert logger.level == original_level


def test_verbose_backtest_enables_debug_and_restores_level():
    original_level = logger.level

    with scoped_backtest_logging(verbose=True):
        assert logger.level == logging.DEBUG

    assert logger.level == original_level
