from datetime import datetime

import pytest

from core.decision import Decision
from core.setup import Setup
from core.trend import Trend
from strategies.qtr_long.decision_engine import LongDecisionEngine
from strategies.qtr_long.risk_manager import LongOnlyRiskManager


def setup(trend: Trend = Trend.BULLISH) -> Setup:
    return Setup(
        index=1,
        timestamp=datetime(2025, 1, 1),
        trend=trend,
        entry=100.0,
        stop_loss=98.0,
    )


def manager() -> LongOnlyRiskManager:
    return LongOnlyRiskManager(risk_reward=2.0, symbol="BTCUSDT", volume=1.0)


def test_long_decision_engine_emits_buy_for_bullish_setup():
    assert LongDecisionEngine().decide(setup()) == Decision.BUY


def test_long_decision_engine_never_converts_bearish_setup_to_sell():
    assert LongDecisionEngine().decide(setup(Trend.BEARISH)) == Decision.SKIP


def test_long_risk_manager_builds_buy_request_only():
    request = manager().build(setup(), Decision.BUY)

    assert request.decision == Decision.BUY
    assert request.take_profit == pytest.approx(104.0)


def test_long_risk_manager_rejects_sell_even_if_it_leaks_downstream():
    with pytest.raises(ValueError, match="BUY requests only"):
        manager().build(setup(), Decision.SELL)


def test_long_risk_manager_rejects_skip():
    with pytest.raises(ValueError, match="BUY requests only"):
        manager().build(setup(), Decision.SKIP)


def test_long_risk_manager_rejects_bearish_setup_even_with_buy_decision():
    with pytest.raises(ValueError, match="bullish setup"):
        manager().build(setup(Trend.BEARISH), Decision.BUY)
