from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backtesting.historical_data import HistoricalDataResult
from backtesting.qtr_long_hierarchy_backtest import (
    QTRLongHierarchyBacktestConfig,
    run_qtr_long_hierarchy_backtest,
)
from backtesting.qtr_long_mtf_historical import QTRLongHistoricalBundle
from core.candle import Candle
from strategies.qtr_long.hierarchy import LongHierarchyStage


BASE = datetime(2026, 1, 1, tzinfo=UTC)
END = BASE + timedelta(hours=8)


def _series(*, minutes: int, count: int, start: datetime = BASE) -> tuple[Candle, ...]:
    return tuple(
        Candle(
            timestamp=start + timedelta(minutes=minutes * index),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1.0,
            index=index,
        )
        for index in range(count)
    )


def _result(candles: tuple[Candle, ...], name: str) -> HistoricalDataResult:
    return HistoricalDataResult(
        candles=candles,
        source="test",
        cache_path=Path(name),
    )


def _bundle() -> QTRLongHistoricalBundle:
    return QTRLongHistoricalBundle(
        category="linear",
        symbol="BTCUSDT",
        start=BASE,
        end=END,
        execution_5m=_result(_series(minutes=5, count=49), "5.json"),
        setup_15m=_result(_series(minutes=15, count=17), "15.json"),
        structure_1h=_result(_series(minutes=60, count=5), "60.json"),
        narrative_4h=_result(_series(minutes=240, count=2), "240.json"),
    )


def test_runs_full_historical_mtf_integration_without_lookahead() -> None:
    result = run_qtr_long_hierarchy_backtest(
        bundle=_bundle(),
        config=QTRLongHierarchyBacktestConfig(symbol="BTCUSDT"),
    )

    assert result.symbol == "BTCUSDT"
    assert result.snapshots_processed == 1
    assert result.buy_plan_count == 0
    assert result.skip_count == 1
    assert sum(result.stage_counts.values()) == 1
    assert result.stage_counts[LongHierarchyStage.NARRATIVE_4H] == 1


def test_config_rejects_empty_symbol_and_invalid_history_window() -> None:
    with pytest.raises(ValueError, match="symbol must not be empty"):
        QTRLongHierarchyBacktestConfig(symbol=" ")

    with pytest.raises(ValueError, match="history_window"):
        QTRLongHierarchyBacktestConfig(symbol="BTCUSDT", history_window=0)
