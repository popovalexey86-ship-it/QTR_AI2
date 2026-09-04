from datetime import datetime

from core.decision import Decision
from core.setup import Setup
from core.trend import Trend
from strategies.qtr_long.decision_engine import LongDecisionEngine


def make_setup(trend: Trend) -> Setup:
    return Setup(
        index=1,
        timestamp=datetime(2025, 1, 1),
        trend=trend,
        entry=100,
        stop_loss=95,
    )


def test_bullish_setup_returns_buy():
    assert LongDecisionEngine().decide(make_setup(Trend.BULLISH)) == Decision.BUY


def test_bearish_setup_never_returns_sell():
    assert LongDecisionEngine().decide(make_setup(Trend.BEARISH)) == Decision.SKIP


def test_range_setup_is_skipped():
    assert LongDecisionEngine().decide(make_setup(Trend.RANGE)) == Decision.SKIP


def test_missing_setup_is_skipped():
    assert LongDecisionEngine().decide(None) == Decision.SKIP
