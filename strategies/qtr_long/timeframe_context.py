from dataclasses import dataclass
from datetime import datetime, timedelta

from core.market_data import MarketData


_EXPECTED_TIMEFRAMES = {
    "execution_5m": "5",
    "setup_15m": "15",
    "structure_1h": "60",
    "narrative_4h": "240",
}


class TimeframeContextError(ValueError):
    """Raised when a QTR Long multi-timeframe context is invalid."""


@dataclass(frozen=True, slots=True)
class QTRLongTimeframeContext:
    """Closed-candle market data required by the hierarchical QTR Long model.

    The execution layer is 5m. Higher timeframes contain only candles that had
    fully closed by the close time of the terminal 5m execution candle.
    """

    execution_5m: MarketData
    setup_15m: MarketData
    structure_1h: MarketData
    narrative_4h: MarketData
    as_of: datetime


class QTRLongTimeframeContextBuilder:
    """Synchronize 5m/15m/1h/4h data without look-ahead bias."""

    def build(
        self,
        *,
        execution_5m: MarketData,
        setup_15m: MarketData,
        structure_1h: MarketData,
        narrative_4h: MarketData,
    ) -> QTRLongTimeframeContext:
        layers = {
            "execution_5m": execution_5m,
            "setup_15m": setup_15m,
            "structure_1h": structure_1h,
            "narrative_4h": narrative_4h,
        }
        self._validate_layers(layers)

        as_of = _last_close_time(execution_5m)
        symbol = execution_5m.symbol

        return QTRLongTimeframeContext(
            execution_5m=_closed_copy(execution_5m, as_of=as_of),
            setup_15m=_closed_copy(setup_15m, as_of=as_of),
            structure_1h=_closed_copy(structure_1h, as_of=as_of),
            narrative_4h=_closed_copy(narrative_4h, as_of=as_of),
            as_of=as_of,
        )

    def _validate_layers(self, layers: dict[str, MarketData]) -> None:
        symbols = {market_data.symbol for market_data in layers.values()}
        if len(symbols) != 1:
            raise TimeframeContextError("All QTR Long timeframe layers must use one symbol")

        for layer_name, market_data in layers.items():
            expected = _EXPECTED_TIMEFRAMES[layer_name]
            if market_data.timeframe != expected:
                raise TimeframeContextError(
                    f"{layer_name} must use timeframe {expected}, got {market_data.timeframe}"
                )
            if not market_data.candles:
                raise TimeframeContextError(f"{layer_name} requires at least one candle")


def _closed_copy(market_data: MarketData, *, as_of: datetime) -> MarketData:
    closed = [
        candle
        for candle in market_data.candles
        if candle.timestamp + _timeframe_delta(market_data.timeframe) <= as_of
    ]
    if not closed:
        raise TimeframeContextError(
            f"No closed {market_data.timeframe} candles are available at {as_of.isoformat()}"
        )

    return MarketData(
        symbol=market_data.symbol,
        timeframe=market_data.timeframe,
        candles=closed,
        loaded_at=as_of,
    )


def _last_close_time(market_data: MarketData) -> datetime:
    return market_data.last.timestamp + _timeframe_delta(market_data.timeframe)


def _timeframe_delta(timeframe: str) -> timedelta:
    try:
        minutes = int(timeframe)
    except ValueError as exc:
        raise TimeframeContextError(f"Unsupported timeframe: {timeframe}") from exc

    if minutes <= 0:
        raise TimeframeContextError(f"Unsupported timeframe: {timeframe}")
    return timedelta(minutes=minutes)
