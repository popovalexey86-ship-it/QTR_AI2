from datetime import UTC, datetime

from core.candle import Candle


class CandleBuilder:
    def __init__(self):
        self._timestamp = datetime.now(UTC)
        self._open = 100.0
        self._high = 100.0
        self._low = 100.0
        self._close = 100.0
        self._volume = 1.0

    def timestamp(self, value: datetime) -> "CandleBuilder":
        self._timestamp = value
        return self

    def open(self, value: float) -> "CandleBuilder":
        self._open = value
        return self

    def high(self, value: float) -> "CandleBuilder":
        self._high = value
        return self

    def low(self, value: float) -> "CandleBuilder":
        self._low = value
        return self

    def close(self, value: float) -> "CandleBuilder":
        self._close = value
        return self

    def volume(self, value: float) -> "CandleBuilder":
        self._volume = value
        return self

    def build(self) -> Candle:
        return Candle(
            timestamp=self._timestamp,
            open=self._open,
            high=self._high,
            low=self._low,
            close=self._close,
            volume=self._volume,
        )