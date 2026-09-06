from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backtesting.qtr_long_execution_backtest import (
    LongExecutionBacktestResult,
    LongExecutionOutcome,
)
from backtesting.qtr_long_hierarchy_runner import QTRLongHierarchyBacktestResult
from strategies.qtr_long.hierarchy import LongHierarchyDecision


@dataclass(frozen=True, slots=True)
class LongForensicTrade:
    plan_time: datetime
    outcome: str
    result_r: float
    entry_source: str
    entry: float
    stop_loss: float
    take_profit: float
    stop_distance_pct: float
    target_distance_pct: float
    fill_delay_minutes: float
    raid_to_displacement_candles: int | None
    displacement_to_plan_candles: int | None
    body_ratio: float | None
    range_expansion: float | None
    close_location: float | None
    execution_trend: str | None
    last_choch: str | None
    last_bos: str | None


def build_qtr_long_filled_forensics(
    *,
    hierarchy_result: QTRLongHierarchyBacktestResult,
    execution_result: LongExecutionBacktestResult,
) -> tuple[LongForensicTrade, ...]:
    """Join BUY_PLAN diagnostics to filled execution outcomes.

    This first forensic layer intentionally uses only information already emitted
    by the frozen Candidate B hierarchy. It therefore cannot invent 4H/1H/15m
    labels that were not persisted in the decision result. Those higher-timeframe
    fields should be instrumented separately before they are used for filtering.
    """
    decision_by_time = {
        decision_time: decision
        for decision_time, decision in zip(
            hierarchy_result.decision_times,
            hierarchy_result.decisions,
            strict=True,
        )
        if decision.decision == LongHierarchyDecision.BUY_PLAN
    }

    rows: list[LongForensicTrade] = []
    for trade in execution_result.trades:
        if trade.outcome not in {LongExecutionOutcome.WIN, LongExecutionOutcome.LOSS}:
            continue

        decision = decision_by_time.get(trade.plan_time)
        if decision is None or decision.entry_plan is None:
            raise RuntimeError("Filled execution trade has no matching BUY_PLAN decision")

        details = _parse_details(decision.details)
        raid_index = _int(details.get("raid_index"))
        displacement_index = _int(details.get("displacement_index"))
        current_index = _int(details.get("current_index"))

        fill_delay_minutes = 0.0
        if trade.fill_time is not None:
            fill_delay_minutes = (trade.fill_time - trade.plan_time).total_seconds() / 60.0

        rows.append(
            LongForensicTrade(
                plan_time=trade.plan_time,
                outcome=trade.outcome.value,
                result_r=trade.result_r,
                entry_source=decision.entry_plan.source.value,
                entry=trade.entry,
                stop_loss=trade.stop_loss,
                take_profit=trade.take_profit,
                stop_distance_pct=(trade.entry - trade.stop_loss) / trade.entry * 100.0,
                target_distance_pct=(trade.take_profit - trade.entry) / trade.entry * 100.0,
                fill_delay_minutes=fill_delay_minutes,
                raid_to_displacement_candles=_delta(displacement_index, raid_index),
                displacement_to_plan_candles=_delta(current_index, displacement_index),
                body_ratio=_float(details.get("body_ratio")),
                range_expansion=_float(details.get("range_expansion")),
                close_location=_float(details.get("close_location")),
                execution_trend=details.get("trend"),
                last_choch=details.get("last_choch"),
                last_bos=details.get("last_bos"),
            )
        )

    return tuple(rows)


def _parse_details(details: str | None) -> dict[str, str]:
    if not details:
        return {}
    parsed: dict[str, str] = {}
    for token in details.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        parsed[key] = value
    return parsed


def _int(value: str | None) -> int | None:
    return int(value) if value is not None else None


def _float(value: str | None) -> float | None:
    return float(value) if value is not None else None


def _delta(later: int | None, earlier: int | None) -> int | None:
    if later is None or earlier is None:
        return None
    return later - earlier
