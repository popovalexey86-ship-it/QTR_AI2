from collections import deque
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta

from backtesting.backtest_runner import BacktestInputError
from core.candle import Candle
from core.market_data import MarketData
from strategies.qtr_long.timeframe_context import (
    QTRLongTimeframeContext,
    QTRLongTimeframeContextBuilder,
)


_TIMEFRAMES = {
    "5": timedelta(minutes=5),
    "15": timedelta(minutes=15),
    "60": timedelta(hours=1),
    "240": timedelta(hours=4),
}


def iter_qtr_long_timeframe_contexts(
    *,
    symbol: str,
    execution_5m: Iterable[Candle],
    setup_15m: Iterable[Candle],
    structure_1h: Iterable[Candle],
    narrative_4h: Iterable[Candle],
    history_window: int = 500,
) -> Iterator[QTRLongTimeframeContext]:
    """Yield synchronized QTR Long 4H/1H/15m/5m contexts without lookahead.

    Each decision point is the close of one 5m execution candle. Higher-timeframe
    candles are admitted only after their own close time is less than or equal to
    that decision time. Initial 5m candles are skipped until every higher layer
    has at least one closed candle available.
    """
    if history_window <= 0:
        raise BacktestInputError("History window must be greater than zero.")
    if not symbol.strip():
        raise BacktestInputError("Symbol must not be empty.")

    execution = _validated_candles(execution_5m, layer="5m")
    setup = _validated_candles(setup_15m, layer="15m")
    structure = _validated_candles(structure_1h, layer="1h")
    narrative = _validated_candles(narrative_4h, layer="4h")

    setup_pos = 0
    structure_pos = 0
    narrative_pos = 0

    execution_history: deque[Candle] = deque(maxlen=history_window)
    setup_history: deque[Candle] = deque(maxlen=history_window)
    structure_history: deque[Candle] = deque(maxlen=history_window)
    narrative_history: deque[Candle] = deque(maxlen=history_window)

    builder = QTRLongTimeframeContextBuilder()

    for candle in execution:
        execution_history.append(candle)
        as_of = candle.timestamp + _TIMEFRAMES["5"]

        setup_pos = _admit_closed(
            setup,
            setup_pos,
            setup_history,
            timeframe="15",
            as_of=as_of,
        )
        structure_pos = _admit_closed(
            structure,
            structure_pos,
            structure_history,
            timeframe="60",
            as_of=as_of,
        )
        narrative_pos = _admit_closed(
            narrative,
            narrative_pos,
            narrative_history,
            timeframe="240",
            as_of=as_of,
        )

        if not setup_history or not structure_history or not narrative_history:
            continue

        yield builder.build(
            execution_5m=_market_data(
                symbol=symbol,
                timeframe="5",
                candles=execution_history,
                loaded_at=as_of,
            ),
            setup_15m=_market_data(
                symbol=symbol,
                timeframe="15",
                candles=setup_history,
                loaded_at=as_of,
            ),
            structure_1h=_market_data(
                symbol=symbol,
                timeframe="60",
                candles=structure_history,
                loaded_at=as_of,
            ),
            narrative_4h=_market_data(
                symbol=symbol,
                timeframe="240",
                candles=narrative_history,
                loaded_at=as_of,
            ),
        )


def _validated_candles(candles: Iterable[Candle], *, layer: str) -> tuple[Candle, ...]:
    result = tuple(candles)
    previous: datetime | None = None
    for candle in result:
        if previous is not None:
            if candle.timestamp == previous:
                raise BacktestInputError(
                    f"Duplicate {layer} candle timestamp: {candle.timestamp.isoformat()}."
                )
            if candle.timestamp < previous:
                raise BacktestInputError(
                    f"Historical {layer} candles must be sorted chronologically."
                )
        previous = candle.timestamp
    return result


def _admit_closed(
    candles: tuple[Candle, ...],
    position: int,
    history: deque[Candle],
    *,
    timeframe: str,
    as_of: datetime,
) -> int:
    delta = _TIMEFRAMES[timeframe]
    while position < len(candles):
        candle = candles[position]
        if candle.timestamp + delta > as_of:
            break
        history.append(candle)
        position += 1
    return position


def _market_data(
    *,
    symbol: str,
    timeframe: str,
    candles: deque[Candle],
    loaded_at: datetime,
) -> MarketData:
    return MarketData(
        symbol=symbol,
        timeframe=timeframe,
        candles=list(candles),
        loaded_at=loaded_at,
    )
