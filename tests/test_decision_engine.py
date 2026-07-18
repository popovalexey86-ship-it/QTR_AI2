from datetime import datetime

from core.decision import Decision
from core.decision_engine import DecisionEngine
from core.setup import Setup
from core.trend import Trend


def make_setup(trend: Trend) -> Setup:
    return Setup(
        index=10,
        timestamp=datetime(2025, 1, 1),
        trend=trend,
        entry=100.0,
        stop_loss=95.0,
    )


def test_skip_when_no_setup():

    engine = DecisionEngine()

    decision = engine.decide(None)

    assert decision == Decision.SKIP


def test_buy_when_bullish_setup():

    engine = DecisionEngine()

    setup = make_setup(Trend.BULLISH)

    decision = engine.decide(setup)

    assert decision == Decision.BUY


def test_sell_when_bearish_setup():

    engine = DecisionEngine()

    setup = make_setup(Trend.BEARISH)

    decision = engine.decide(setup)

    assert decision == Decision.SELL
