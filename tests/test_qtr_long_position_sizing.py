import pytest

from strategies.qtr_long.position_sizing import LongPositionSizer
from strategies.qtr_long.risk import LongRiskPlan


def plan(*, entry=100.0, stop=98.0, risk_pct=0.5):
    risk = entry - stop
    return LongRiskPlan(
        entry=entry,
        stop_loss=stop,
        take_profit=entry + risk * 2,
        risk_per_unit=risk,
        reward_per_unit=risk * 2,
        risk_reward=2.0,
        risk_per_trade_pct=risk_pct,
    )


def test_sizes_position_from_equity_and_stop_distance():
    result = LongPositionSizer().calculate(plan(), equity=10_000)

    # 0.5% of 10,000 = 50 risk. A 2 dollar stop permits 25 units.
    assert result.risk_amount == pytest.approx(50)
    assert result.quantity == pytest.approx(25)
    assert result.notional == pytest.approx(2_500)
    assert result.effective_risk_pct == pytest.approx(0.5)


def test_wider_stop_reduces_quantity_while_preserving_dollar_risk():
    result = LongPositionSizer().calculate(
        plan(entry=100, stop=95),
        equity=10_000,
    )

    assert result.quantity == pytest.approx(10)
    assert result.risk_amount == pytest.approx(50)


def test_notional_cap_reduces_effective_risk_instead_of_exceeding_exposure():
    result = LongPositionSizer(maximum_notional_pct=10).calculate(
        plan(entry=100, stop=99.9),
        equity=10_000,
    )

    assert result.notional == pytest.approx(1_000)
    assert result.quantity == pytest.approx(10)
    assert result.risk_amount == pytest.approx(1)
    assert result.effective_risk_pct == pytest.approx(0.01)


def test_rejects_invalid_equity():
    with pytest.raises(ValueError):
        LongPositionSizer().calculate(plan(), equity=0)
