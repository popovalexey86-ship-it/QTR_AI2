from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
import math

from core.candle import Candle


class HistoricalDataError(RuntimeError):
    """Raised when public historical market data is invalid or unavailable."""


SUPPORTED_INTERVALS = frozenset(
    {
        "1", "3", "5", "15", "30", "60", "120", "240", "360", "720",
        "D", "W", "M",
    }
)


def candle_close_time(timestamp: datetime, interval: str) -> datetime:
    if interval.isdigit():
        return timestamp + timedelta(minutes=int(interval))
    if interval == "D":
        return timestamp + timedelta(days=1)
    if interval == "W":
        return timestamp + timedelta(days=7)
    if interval == "M":
        year = timestamp.year + (1 if timestamp.month == 12 else 0)
        month = 1 if timestamp.month == 12 else timestamp.month + 1
        return timestamp.replace(year=year, month=month, day=1)
    raise HistoricalDataError("Unsupported historical candle interval.")


class BybitHistoricalMapper:
    @staticmethod
    def map_rows(
        rows: Sequence[object],
        *,
        interval: str,
        start: datetime,
        effective_end: datetime,
    ) -> tuple[Candle, ...]:
        mapped: dict[datetime, Candle] = {}

        for row_number, raw_row in enumerate(rows, start=1):
            candle = BybitHistoricalMapper._map_row(raw_row, row_number)
            if not start <= candle.timestamp < effective_end:
                continue
            if candle_close_time(candle.timestamp, interval) > effective_end:
                continue

            existing = mapped.get(candle.timestamp)
            if existing is not None and existing != candle:
                raise HistoricalDataError(
                    "Conflicting historical candles share one timestamp."
                )
            mapped[candle.timestamp] = candle

        candles = sorted(mapped.values(), key=lambda candle: candle.timestamp)
        return tuple(
            Candle(
                timestamp=candle.timestamp,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                index=index,
            )
            for index, candle in enumerate(candles)
        )

    @staticmethod
    def _map_row(raw_row: object, row_number: int) -> Candle:
        if not isinstance(raw_row, (list, tuple)) or len(raw_row) < 6:
            raise HistoricalDataError(
                f"Malformed historical candle at row {row_number}."
            )

        try:
            timestamp_ms = int(raw_row[0])
            open_price = float(raw_row[1])
            high = float(raw_row[2])
            low = float(raw_row[3])
            close = float(raw_row[4])
            volume = float(raw_row[5])
        except (TypeError, ValueError, OverflowError):
            raise HistoricalDataError(
                f"Malformed historical candle at row {row_number}."
            ) from None

        values = (open_price, high, low, close, volume)
        if timestamp_ms < 0 or not all(math.isfinite(value) for value in values):
            raise HistoricalDataError(
                f"Invalid historical candle values at row {row_number}."
            )
        if high < max(open_price, close, low):
            raise HistoricalDataError(
                f"Invalid high price at historical row {row_number}."
            )
        if low > min(open_price, close, high):
            raise HistoricalDataError(
                f"Invalid low price at historical row {row_number}."
            )
        if volume < 0:
            raise HistoricalDataError(
                f"Negative volume at historical row {row_number}."
            )

        try:
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
        except (OSError, OverflowError, ValueError):
            raise HistoricalDataError(
                f"Invalid timestamp at historical row {row_number}."
            ) from None

        return Candle(
            timestamp=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )
