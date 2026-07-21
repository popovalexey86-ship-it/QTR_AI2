from datetime import UTC, datetime, timedelta

from backtesting.bootstrap import create_backtest_runner
from backtesting.logging import scoped_backtest_logging
from backtesting.snapshots import iter_market_data_snapshots
from core.candle import Candle


def test_real_smc_backtest_has_no_raw_setup_diagnostics(capsys):
    start = datetime(2025, 1, 1, tzinfo=UTC)
    candles = []
    for index in range(21):
        high = 101.0
        low = 99.0
        close = 100.0
        if index == 2:
            high = 110.0
        elif index == 7:
            low = 90.0
        elif index == 12:
            high = 115.0
        elif index == 17:
            low = 95.0
        elif index == 20:
            high = 117.0
            low = 100.0
            close = 116.0
        candles.append(
            Candle(
                timestamp=start + timedelta(minutes=15 * index),
                open=100.0,
                high=high,
                low=low,
                close=close,
                volume=1.0,
                index=index,
            )
        )

    snapshots = iter_market_data_snapshots(
        candles,
        symbol="BTCUSDT",
        interval="15",
        history_window=100,
    )
    with scoped_backtest_logging():
        result = create_backtest_runner("BTCUSDT").run(snapshots)

    output = capsys.readouterr().out
    assert result.has_open_position is False
    assert result.has_pending_entry is True
    assert "Trend:" not in output
    assert "Last HL:" not in output
    assert "Last LH:" not in output
    assert "=" * 60 not in output
