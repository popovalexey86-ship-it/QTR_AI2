from datetime import datetime

from core.liquidity_sweep import LiquiditySweep, LiquiditySweepDirection
from core.order_block import OrderBlock, OrderBlockDirection
from strategies.qtr_long.risk import LongRiskGate
from strategies.qtr_long.score import LongScore
from strategies.qtr_long.setup import LongSetupCandidate, LongSetupType


def score(total_high: bool = True) -> LongScore:
    if total_high:
        return LongScore(25, 20, 15, 10, 10, 10, 10)
    return LongScore(10, 15, 5, 0, 0, 0, 0)


def candidate(entry=100.0, stop=98.0) -> LongSetupCandidate:
    sweep = LiquiditySweep(
        index=1,
        timestamp=datetime(2025, 1, 1),
        direction=LiquiditySweepDirection.BULLISH,
        swept_price=99.0,
        extreme_price=98.0,
        reclaim_close=100.0,
    )
    order_block = OrderBlock(
        index=1,
        timestamp=datetime(2025, 1, 1),
        direction=OrderBlockDirection.BULLISH,
        low=98.5,
        high=99.5,
    )
    return LongSetupCandidate(
        type=LongSetupType.SWEEP_RECLAIM_ORDER_BLOCK,
        liquidity_sweep=sweep,
        order_block=order_block,
        entry=entry,
        stop_loss=stop,
    )


def test_approves_valid_long_geometry_and_builds_two_r_target():
    plan = LongRiskGate().evaluate(candidate(), score())

    assert plan is not None
    assert plan.entry == 100
    assert plan.stop_loss == 98
    assert plan.risk_per_unit == 2
    assert plan.take_profit == 104
    assert plan.risk_reward == 2.0
    assert plan.risk_per_trade_pct == 0.5


def test_rejects_candidate_below_minimum_score():
    assert LongRiskGate().evaluate(candidate(), score(False)) is None


def test_rejects_stop_that_is_too_far_away():
    gate = LongRiskGate(maximum_stop_distance_pct=5.0)
    assert gate.evaluate(candidate(entry=100, stop=90), score()) is None
