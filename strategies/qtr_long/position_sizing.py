import math
from dataclasses import dataclass

from strategies.qtr_long.risk import LongRiskPlan


@dataclass(frozen=True, slots=True)
class LongPositionSize:
    """Account-based size for an approved QTR Long risk plan."""

    equity: float
    risk_amount: float
    quantity: float
    notional: float
    entry: float
    stop_loss: float
    risk_per_unit: float
    effective_risk_pct: float


class LongPositionSizer:
    """Convert a risk plan into quantity without changing the stop geometry."""

    def __init__(self, *, maximum_notional_pct: float = 100.0) -> None:
        if not 0 < maximum_notional_pct <= 100:
            raise ValueError("maximum_notional_pct must be in (0, 100]")
        self._maximum_notional_pct = float(maximum_notional_pct)

    def calculate(self, plan: LongRiskPlan, equity: float) -> LongPositionSize:
        if not math.isfinite(equity) or equity <= 0:
            raise ValueError("equity must be finite and positive")
        if plan.entry <= 0 or plan.risk_per_unit <= 0:
            raise ValueError("risk plan must have positive entry and risk per unit")

        requested_risk = equity * plan.risk_per_trade_pct / 100
        risk_quantity = requested_risk / plan.risk_per_unit

        maximum_notional = equity * self._maximum_notional_pct / 100
        notional_quantity = maximum_notional / plan.entry
        quantity = min(risk_quantity, notional_quantity)

        risk_amount = quantity * plan.risk_per_unit
        notional = quantity * plan.entry
        effective_risk_pct = risk_amount / equity * 100

        return LongPositionSize(
            equity=float(equity),
            risk_amount=risk_amount,
            quantity=quantity,
            notional=notional,
            entry=plan.entry,
            stop_loss=plan.stop_loss,
            risk_per_unit=plan.risk_per_unit,
            effective_risk_pct=effective_risk_pct,
        )
