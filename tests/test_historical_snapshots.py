from datetime import UTC, datetime, timedelta

from backtesting.snapshots import iter_market_data_snapshots
from core.candle import Candle


START = datetime(2025, 1, 1, tzinfo=UTC)


def candles(count: int):
    for index in range(count):
        yield Candle(
            timestamp=START + timedelta(minutes=index),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1.0,
            index=index,
        )


def test_snapshots_have_no_look_ahead():
    snapshots = iter_market_data_snapshots(
        candles(4),
        symbol="BTCUSDT",
        interval="1",
        history_window=10,
    )

    for expected_index, snapshot in enumerate(snapshots):
        assert snapshot.last.index == expected_index
        assert all(candle.index <= expected_index for candle in snapshot.candles)


def test_snapshots_use_bounded_rolling_history():
    snapshots = list(
        iter_market_data_snapshots(
            candles(5),
            symbol="BTCUSDT",
            interval="1",
            history_window=2,
        )
    )

    assert [len(snapshot.candles) for snapshot in snapshots] == [1, 2, 2, 2, 2]
    assert [candle.index for candle in snapshots[-1].candles] == [3, 4]
