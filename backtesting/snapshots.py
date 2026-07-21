from collections import deque
from collections.abc import Iterable, Iterator

from backtesting.backtest_runner import BacktestInputError
from core.candle import Candle
from core.market_data import MarketData


def iter_market_data_snapshots(
    candles: Iterable[Candle],
    *,
    symbol: str,
    interval: str,
    history_window: int = 500,
) -> Iterator[MarketData]:
    """Yield bounded snapshots containing no candle after the terminal candle."""
    if history_window <= 0:
        raise BacktestInputError("History window must be greater than zero.")

    history: deque[Candle] = deque(maxlen=history_window)
    previous_timestamp = None

    for candle in candles:
        if previous_timestamp is not None:
            if candle.timestamp == previous_timestamp:
                raise BacktestInputError(
                    f"Duplicate candle timestamp: {candle.timestamp.isoformat()}."
                )
            if candle.timestamp < previous_timestamp:
                raise BacktestInputError(
                    "Historical candles must be sorted chronologically."
                )
        history.append(candle)
        previous_timestamp = candle.timestamp
        yield MarketData(
            symbol=symbol,
            timeframe=interval,
            candles=list(history),
            loaded_at=candle.timestamp,
        )
