from collections.abc import Callable
from datetime import UTC, datetime
import re
from typing import Any

import requests

from core.candle import Candle
from infrastructure.bybit.bybit_historical_mapper import (
    BybitHistoricalMapper,
    HistoricalDataError,
    SUPPORTED_INTERVALS,
)


PUBLIC_KLINE_URL = "https://api.bybit.com/v5/market/kline"
MAX_PAGE_SIZE = 1000
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]+$")


class BybitHistoricalClient:
    """Credential-free client for the public Bybit V5 kline endpoint."""

    def __init__(
        self,
        session: requests.Session | None = None,
        timeout: tuple[float, float] = (3.05, 15.0),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session or requests.Session()
        self._timeout = timeout
        self._clock = clock or (lambda: datetime.now(UTC))

    def fetch_candles(
        self,
        *,
        category: str,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]:
        start, end = self.validate_request(
            category=category,
            symbol=symbol,
            interval=interval,
            start=start,
            end=end,
        )
        now = self._require_utc(self._clock(), "Current time")
        effective_end = min(end, now)
        if effective_end <= start:
            return ()

        start_ms = int(start.timestamp() * 1000)
        cursor_end_ms = int(effective_end.timestamp() * 1000)
        rows: list[object] = []

        while cursor_end_ms > start_ms:
            page = self._request_page(
                category=category,
                symbol=symbol,
                interval=interval,
                start_ms=start_ms,
                end_ms=cursor_end_ms - 1,
            )
            if not page:
                break

            rows.extend(page)
            oldest_ms = self._oldest_timestamp(page)
            if oldest_ms <= start_ms:
                break
            if oldest_ms >= cursor_end_ms:
                raise HistoricalDataError(
                    "Historical pagination cursor did not advance."
                )
            cursor_end_ms = oldest_ms

        return BybitHistoricalMapper.map_rows(
            rows,
            interval=interval,
            start=start,
            effective_end=effective_end,
        )

    def _request_page(
        self,
        *,
        category: str,
        symbol: str,
        interval: str,
        start_ms: int,
        end_ms: int,
    ) -> list[object]:
        params: dict[str, str | int] = {
            "category": category,
            "symbol": symbol,
            "interval": interval,
            "start": start_ms,
            "end": end_ms,
            "limit": MAX_PAGE_SIZE,
        }
        try:
            response = self._session.get(
                PUBLIC_KLINE_URL,
                params=params,
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload: Any = response.json()
        except requests.RequestException:
            raise HistoricalDataError(
                "Bybit historical request failed."
            ) from None
        except ValueError:
            raise HistoricalDataError(
                "Bybit historical response is not valid JSON."
            ) from None

        if not isinstance(payload, dict):
            raise HistoricalDataError("Malformed Bybit historical response.")
        if payload.get("retCode") != 0:
            raise HistoricalDataError("Bybit rejected the historical request.")

        result = payload.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("list"), list):
            raise HistoricalDataError("Malformed Bybit historical response.")
        return result["list"]

    @staticmethod
    def _oldest_timestamp(page: list[object]) -> int:
        timestamps: list[int] = []
        for row in page:
            if not isinstance(row, (list, tuple)) or not row:
                raise HistoricalDataError("Malformed historical candle row.")
            try:
                timestamps.append(int(row[0]))
            except (TypeError, ValueError, OverflowError):
                raise HistoricalDataError(
                    "Malformed historical candle timestamp."
                ) from None
        return min(timestamps)

    @classmethod
    def validate_request(
        cls,
        *,
        category: str,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> tuple[datetime, datetime]:
        if category != "linear":
            raise HistoricalDataError(
                "Only the linear historical category is supported."
            )
        if not _SYMBOL_PATTERN.fullmatch(symbol) or symbol != symbol.upper():
            raise HistoricalDataError(
                "Historical symbol must be a non-empty uppercase symbol."
            )
        if interval not in SUPPORTED_INTERVALS:
            raise HistoricalDataError("Unsupported historical candle interval.")

        start = cls._require_utc(start, "Start")
        end = cls._require_utc(end, "End")
        if start >= end:
            raise HistoricalDataError("Historical start must be earlier than end.")
        return start, end

    @staticmethod
    def _require_utc(value: datetime, label: str) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise HistoricalDataError(f"{label} datetime must be timezone-aware UTC.")
        if value.utcoffset() != UTC.utcoffset(value):
            raise HistoricalDataError(f"{label} datetime must use UTC.")
        return value.astimezone(UTC)
