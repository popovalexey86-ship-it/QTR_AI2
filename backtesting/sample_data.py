from datetime import UTC, datetime, timedelta

from core.candle import Candle
from core.market_data import MarketData


def create_sample_snapshots() -> tuple[MarketData, ...]:
    """Return fixed, in-memory BTCUSDT snapshots for the safe sample CLI."""
    start = datetime(2025, 1, 1, tzinfo=UTC)
    candles = tuple(
        Candle(
            timestamp=start + timedelta(minutes=15 * index),
            open=100_000.0 + index * 50.0,
            high=100_100.0 + index * 50.0,
            low=99_900.0 + index * 50.0,
            close=100_050.0 + index * 50.0,
            volume=1_000.0,
            index=index,
        )
        for index in range(10)
    )

    return tuple(
        MarketData(
            symbol="BTCUSDT",
            timeframe="15m",
            candles=list(candles[: index + 1]),
            loaded_at=candles[index].timestamp,
        )
        for index in range(len(candles))
    )
