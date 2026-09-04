from dataclasses import dataclass

from strategies.qtr_long.score import LongScore
from strategies.qtr_long.setup import LongSetupCandidate


@dataclass(frozen=True, slots=True)
class LongRiskPlan:
    """Approved long-only risk geometry before account-based position sizing."""

    entry: float
    stop_loss: float
    take_profit: float
    risk_per_unit: float
    reward_per_unit: float
    risk_reward: float
    risk_per_trade_pct: float


class LongRiskGate:
    """Reject unsafe QTR Long candidates before execution.

    This layer validates price geometry and minimum model quality. It does not
    calculate order quantity because account equity is intentionally outside
    the strategy-analysis context.
    """

    def __init__(
        self,
        *,
        minimum_score: int = 80,
        minimum_risk_reward: float = 2.0,
        risk_per_trade_pct: float = 0.5,
        maximum_stop_distance_pct: float = 5.0,
    ) -> None:
        if not 0 <= minimum_score <= 100:
            raise ValueError("minimum_score must be between 0 and 100")
        if minimum_risk_reward <= 0:
            raise ValueError("minimum_risk_reward must be positive")
        if not 0 < risk_per_trade_pct <= 100:
            raise ValueError("risk_per_trade_pct must be in (0, 100]")
        if maximum_stop_distance_pct <= 0:
            raise ValueError("maximum_stop_distance_pct must be positive")

        self._minimum_score = minimum_score
        self._minimum_risk_reward = float(minimum_risk_reward)
        self._risk_per_trade_pct = float(risk_per_trade_pct)
        self._maximum_stop_distance_pct = float(maximum_stop_distance_pct)

    def evaluate(
        self,
        candidate: LongSetupCandidate,
        score: LongScore,
    ) -> LongRiskPlan | None:
        if score.total < self._minimum_score:
            return None

        entry = candidate.entry
        stop_loss = candidate.stop_loss
        if entry <= 0 or stop_loss <= 0 or stop_loss >= entry:
            return None

        risk = entry - stop_loss
        stop_distance_pct = risk / entry * 100
        if stop_distance_pct > self._maximum_stop_distance_pct:
            return None

        reward = risk * self._minimum_risk_reward
        take_profit = entry + reward

        return LongRiskPlan(
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_per_unit=risk,
            reward_per_unit=reward,
            risk_reward=self._minimum_risk_reward,
            risk_per_trade_pct=self._risk_per_trade_pct,
        )
