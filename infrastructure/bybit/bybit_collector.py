from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from core.exceptions import BrokerError
from core.market_data import MarketData

from infrastructure.bybit.bybit_client import BybitClient
from infrastructure.bybit.bybit_mapper import BybitMapper


class BybitCompletedCandleError(BrokerError):
    """Raised when completed live candles cannot be collected safely."""


class BybitCollector:

    def __init__(
        self,
        client: BybitClient,
        category: str = "linear",
        symbol: str = "BTCUSDT",
        interval: str = "1",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._category = category
        self._symbol = symbol
        self._interval = interval
        self._clock = clock or (lambda: datetime.now(UTC))

    def collect(
        self,
        category: str | None = None,
        symbol: str | None = None,
        interval: str | None = None,
        limit: int = 500,
    ) -> MarketData:

        category = category or self._category
        symbol = symbol or self._symbol
        interval = interval or self._interval

        response = self._client.get_klines(
            category=category,
            symbol=symbol,
            interval=interval,
            limit=limit,
        )

        return BybitMapper.to_market_data(
            response=response,
            symbol=symbol,
            timeframe=interval,
        )

    def collect_completed(
        self,
        category: str | None = None,
        symbol: str | None = None,
        interval: str | None = None,
        limit: int = 500,
    ) -> MarketData:
        selected_category = category or self._category
        selected_symbol = symbol or self._symbol
        selected_interval = interval or self._interval
        interval_duration = _numeric_minute_interval(selected_interval)
        current_time = self._clock()
        _validate_utc_time(current_time)

        market_data = self.collect(
            category=selected_category,
            symbol=selected_symbol,
            interval=selected_interval,
            limit=limit,
        )
        completed = [
            candle
            for candle in market_data.candles
            if candle.timestamp + interval_duration <= current_time
        ]
        if not completed:
            raise BybitCompletedCandleError(
                "Bybit returned no completed candles for live processing."
            )
        return MarketData(
            symbol=market_data.symbol,
            timeframe=market_data.timeframe,
            candles=completed,
            loaded_at=market_data.loaded_at,
        )


def _numeric_minute_interval(interval: str) -> timedelta:
    normalized = interval.strip()
    if not normalized.isascii() or not normalized.isdecimal():
        raise BybitCompletedCandleError(
            "Unsupported live candle interval."
        )
    minutes = int(normalized)
    if minutes <= 0:
        raise BybitCompletedCandleError(
            "Unsupported live candle interval."
        )
    return timedelta(minutes=minutes)


def _validate_utc_time(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise BybitCompletedCandleError(
            "Live candle clock must be timezone-aware UTC."
        )
    if value.utcoffset() != timedelta(0):
        raise BybitCompletedCandleError(
            "Live candle clock must use UTC."
        )
