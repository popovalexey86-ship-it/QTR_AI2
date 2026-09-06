from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import prod

from backtesting.qtr_long_hierarchy_runner import QTRLongHierarchyBacktestResult
from core.candle import Candle
from strategies.qtr_long.execution_entry import LongExecutionEntryPlan
from strategies.qtr_long.hierarchy import LongHierarchyDecision


class LongExecutionOutcome(Enum):
    WIN = "win"
    LOSS = "loss"
    EXPIRED = "expired"
    OPEN = "open"


@dataclass(frozen=True, slots=True)
class LongExecutionTrade:
    plan_time: datetime
    entry: float
    stop_loss: float
    take_profit: float
    risk_per_unit: float
    outcome: LongExecutionOutcome
    fill_time: datetime | None
    exit_time: datetime | None
    result_r: float


@dataclass(frozen=True, slots=True)
class LongExecutionBacktestConfig:
    rr: float = 2.0
    pending_ttl_candles: int = 12
    risk_pct: float = 0.005
    initial_equity: float = 10_000.0

    def __post_init__(self) -> None:
        if self.rr <= 0:
            raise ValueError("rr must be greater than zero")
        if self.pending_ttl_candles < 1:
            raise ValueError("pending_ttl_candles must be at least one")
        if not 0 < self.risk_pct < 1:
            raise ValueError("risk_pct must be in (0, 1)")
        if self.initial_equity <= 0:
            raise ValueError("initial_equity must be greater than zero")


@dataclass(frozen=True, slots=True)
class LongExecutionBacktestResult:
    plans: int
    filled: int
    expired: int
    wins: int
    losses: int
    open_count: int
    win_rate: float
    net_r: float
    expectancy_r: float
    profit_factor: float | None
    max_drawdown_pct: float
    initial_equity: float
    final_equity: float
    trades: tuple[LongExecutionTrade, ...]


def run_qtr_long_execution_backtest(
    *,
    hierarchy_result: QTRLongHierarchyBacktestResult,
    execution_candles: tuple[Candle, ...] | list[Candle],
    config: LongExecutionBacktestConfig = LongExecutionBacktestConfig(),
) -> LongExecutionBacktestResult:
    """Simulate the frozen Candidate B BUY plans on closed 5m candles.

    Contract:
    - the limit order becomes eligible only on the first candle whose open time
      is at or after the BUY_PLAN decision time (the candle after confirmation);
    - the pending BUY expires after ``pending_ttl_candles`` 5m candles;
    - TP is fixed at ``entry + rr * (entry - stop)``;
    - if SL and TP are both touched in one candle, SL wins (conservative OHLC rule);
    - unfilled plans are EXPIRED and positions still alive at the dataset end are OPEN;
    - results are expressed in R. Equity compounds fixed-fractional risk on closed trades.

    The first execution study deliberately excludes fees, funding and slippage.
    """
    candles = tuple(execution_candles)
    if not candles:
        raise ValueError("execution_candles must not be empty")

    plan_events: list[tuple[datetime, LongExecutionEntryPlan]] = []
    for decision_time, decision in zip(
        hierarchy_result.decision_times,
        hierarchy_result.decisions,
        strict=True,
    ):
        if decision.decision != LongHierarchyDecision.BUY_PLAN:
            continue
        if decision.entry_plan is None:
            raise RuntimeError("BUY_PLAN is missing entry_plan")
        plan_events.append((decision_time, decision.entry_plan))

    trades = tuple(
        _simulate_plan(
            plan_time=plan_time,
            plan=plan,
            candles=candles,
            config=config,
        )
        for plan_time, plan in plan_events
    )

    wins = sum(trade.outcome == LongExecutionOutcome.WIN for trade in trades)
    losses = sum(trade.outcome == LongExecutionOutcome.LOSS for trade in trades)
    expired = sum(trade.outcome == LongExecutionOutcome.EXPIRED for trade in trades)
    open_count = sum(trade.outcome == LongExecutionOutcome.OPEN for trade in trades)
    filled = wins + losses + open_count
    closed = wins + losses

    net_r = sum(trade.result_r for trade in trades)
    expectancy_r = net_r / closed if closed else 0.0
    win_rate = wins / closed if closed else 0.0
    gross_profit_r = sum(max(trade.result_r, 0.0) for trade in trades)
    gross_loss_r = -sum(min(trade.result_r, 0.0) for trade in trades)
    profit_factor = gross_profit_r / gross_loss_r if gross_loss_r > 0 else None

    equity_curve = [config.initial_equity]
    equity = config.initial_equity
    for trade in trades:
        if trade.outcome not in {LongExecutionOutcome.WIN, LongExecutionOutcome.LOSS}:
            continue
        equity *= 1.0 + config.risk_pct * trade.result_r
        equity_curve.append(equity)

    peak = equity_curve[0]
    max_drawdown_pct = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        drawdown = (peak - value) / peak
        max_drawdown_pct = max(max_drawdown_pct, drawdown)

    return LongExecutionBacktestResult(
        plans=len(trades),
        filled=filled,
        expired=expired,
        wins=wins,
        losses=losses,
        open_count=open_count,
        win_rate=win_rate,
        net_r=net_r,
        expectancy_r=expectancy_r,
        profit_factor=profit_factor,
        max_drawdown_pct=max_drawdown_pct,
        initial_equity=config.initial_equity,
        final_equity=equity,
        trades=trades,
    )


def _simulate_plan(
    *,
    plan_time: datetime,
    plan: LongExecutionEntryPlan,
    candles: tuple[Candle, ...],
    config: LongExecutionBacktestConfig,
) -> LongExecutionTrade:
    risk_per_unit = plan.entry - plan.stop_loss
    if risk_per_unit <= 0:
        raise ValueError("entry plan must have positive risk distance")
    take_profit = plan.entry + config.rr * risk_per_unit

    eligible = [candle for candle in candles if candle.timestamp >= plan_time]
    pending = eligible[: config.pending_ttl_candles]

    fill_position: int | None = None
    fill_candle: Candle | None = None
    for position, candle in enumerate(pending):
        if candle.low <= plan.entry <= candle.high:
            fill_position = position
            fill_candle = candle
            break

    if fill_candle is None or fill_position is None:
        return LongExecutionTrade(
            plan_time=plan_time,
            entry=plan.entry,
            stop_loss=plan.stop_loss,
            take_profit=take_profit,
            risk_per_unit=risk_per_unit,
            outcome=LongExecutionOutcome.EXPIRED,
            fill_time=None,
            exit_time=None,
            result_r=0.0,
        )

    # The fill candle is eligible for exit. When both barriers are inside the
    # same OHLC candle, assume the adverse barrier was reached first.
    post_fill = eligible[fill_position:]
    for candle in post_fill:
        stop_hit = candle.low <= plan.stop_loss
        target_hit = candle.high >= take_profit
        if stop_hit:
            return LongExecutionTrade(
                plan_time=plan_time,
                entry=plan.entry,
                stop_loss=plan.stop_loss,
                take_profit=take_profit,
                risk_per_unit=risk_per_unit,
                outcome=LongExecutionOutcome.LOSS,
                fill_time=fill_candle.timestamp,
                exit_time=candle.timestamp,
                result_r=-1.0,
            )
        if target_hit:
            return LongExecutionTrade(
                plan_time=plan_time,
                entry=plan.entry,
                stop_loss=plan.stop_loss,
                take_profit=take_profit,
                risk_per_unit=risk_per_unit,
                outcome=LongExecutionOutcome.WIN,
                fill_time=fill_candle.timestamp,
                exit_time=candle.timestamp,
                result_r=config.rr,
            )

    return LongExecutionTrade(
        plan_time=plan_time,
        entry=plan.entry,
        stop_loss=plan.stop_loss,
        take_profit=take_profit,
        risk_per_unit=risk_per_unit,
        outcome=LongExecutionOutcome.OPEN,
        fill_time=fill_candle.timestamp,
        exit_time=None,
        result_r=0.0,
    )
