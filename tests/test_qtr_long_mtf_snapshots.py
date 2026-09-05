from datetime import UTC, datetime, timedelta

import pytest

from backtesting.backtest_runner import BacktestInputError
from backtesting.qtr_long_mtf_snapshots import iter_qtr_long_timeframe_contexts
from core.candle import Candle


BASE = datetime(2026, 1, 1, tzinfo=UTC)


def _candle(timestamp: datetime, index: int) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1.0,
        index=index,
    )


def _series(*, start: datetime, minutes: int, count: int) -> list[Candle]:
    return [
        _candle(start + timedelta(minutes=minutes * index), index)
        for index in range(count)
    ]


def test_yields_only_after_all_higher_timeframes_have_closed_data() -> None:
    contexts = list(
        iter_qtr_long_timeframe_contexts(
            symbol="BTCUSDT",
            execution_5m=_series(start=BASE, minutes=5, count=49),
            setup_15m=_series(start=BASE, minutes=15, count=17),
            structure_1h=_series(start=BASE, minutes=60, count=5),
            narrative_4h=_series(start=BASE, minutes=240, count=2),
        )
    )

    assert len(contexts) == 1
    assert contexts[0].as_of == BASE + timedelta(hours=4, minutes=5)


def test_excludes_in_progress_higher_timeframe_candles() -> None:
    contexts = list(
        iter_qtr_long_timeframe_contexts(
            symbol="BTCUSDT",
            execution_5m=_series(start=BASE, minutes=5, count=50),
            setup_15m=_series(start=BASE, minutes=15, count=18),
            structure_1h=_series(start=BASE, minutes=60, count=6),
            narrative_4h=_series(start=BASE, minutes=240, count=2),
        )
    )

    context = contexts[-1]
    assert context.as_of == BASE + timedelta(hours=4, minutes=10)
    assert context.setup_15m.last.timestamp == BASE + timedelta(hours=3, minutes=45)
    assert context.structure_1h.last.timestamp == BASE + timedelta(hours=3)
    assert context.narrative_4h.last.timestamp == BASE


def test_admits_higher_timeframe_candle_exactly_at_its_close() -> None:
    contexts = list(
        iter_qtr_long_timeframe_contexts(
            symbol="BTCUSDT",
            execution_5m=_series(start=BASE, minutes=5, count=48),
            setup_15m=_series(start=BASE, minutes=15, count=16),
            structure_1h=_series(start=BASE, minutes=60, count=4),
            narrative_4h=_series(start=BASE, minutes=240, count=1),
        )
    )

    context = contexts[-1]
    assert context.as_of == BASE + timedelta(hours=4)
    assert context.narrative_4h.last.timestamp == BASE


def test_history_window_bounds_every_layer() -> None:
    contexts = list(
        iter_qtr_long_timeframe_contexts(
            symbol="BTCUSDT",
            execution_5m=_series(start=BASE, minutes=5, count=100),
            setup_15m=_series(start=BASE, minutes=15, count=40),
            structure_1h=_series(start=BASE, minutes=60, count=10),
            narrative_4h=_series(start=BASE - timedelta(hours=8), minutes=240, count=5),
            history_window=3,
        )
    )

    context = contexts[-1]
    assert len(context.execution_5m.candles) == 3
    assert len(context.setup_15m.candles) == 3
    assert len(context.structure_1h.candles) == 3
    assert len(context.narrative_4h.candles) == 3


def test_rejects_duplicate_timestamp_in_any_layer() -> None:
    duplicate_15m = [
        _candle(BASE, 0),
        _candle(BASE, 1),
    ]

    with pytest.raises(BacktestInputError, match="Duplicate 15m candle timestamp"):
        list(
            iter_qtr_long_timeframe_contexts(
                symbol="BTCUSDT",
                execution_5m=_series(start=BASE, minutes=5, count=2),
                setup_15m=duplicate_15m,
                structure_1h=_series(start=BASE, minutes=60, count=1),
                narrative_4h=_series(start=BASE, minutes=240, count=1),
            )
        )


def test_rejects_unsorted_execution_data() -> None:
    execution = [
        _candle(BASE + timedelta(minutes=5), 1),
        _candle(BASE, 0),
    ]

    with pytest.raises(BacktestInputError, match="5m candles must be sorted"):
        list(
            iter_qtr_long_timeframe_contexts(
                symbol="BTCUSDT",
                execution_5m=execution,
                setup_15m=_series(start=BASE, minutes=15, count=1),
                structure_1h=_series(start=BASE, minutes=60, count=1),
                narrative_4h=_series(start=BASE, minutes=240, count=1),
            )
        )


def test_rejects_invalid_history_window_and_empty_symbol() -> None:
    with pytest.raises(BacktestInputError, match="History window"):
        list(
            iter_qtr_long_timeframe_contexts(
                symbol="BTCUSDT",
                execution_5m=[],
                setup_15m=[],
                structure_1h=[],
                narrative_4h=[],
                history_window=0,
            )
        )

    with pytest.raises(BacktestInputError, match="Symbol must not be empty"):
        list(
            iter_qtr_long_timeframe_contexts(
                symbol=" ",
                execution_5m=[],
                setup_15m=[],
                structure_1h=[],
                narrative_4h=[],
            )
        )
