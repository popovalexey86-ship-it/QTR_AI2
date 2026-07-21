from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from core.candle import Candle
from infrastructure.bybit.bybit_historical_client import BybitHistoricalClient
from infrastructure.bybit.bybit_historical_mapper import (
    BybitHistoricalMapper,
    HistoricalDataError,
)


class HistoricalCacheError(HistoricalDataError):
    """Raised when a historical cache file is corrupt or cannot be written."""


@dataclass(frozen=True, slots=True)
class HistoricalRequest:
    category: str
    symbol: str
    interval: str
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        BybitHistoricalClient.validate_request(
            category=self.category,
            symbol=self.symbol,
            interval=self.interval,
            start=self.start,
            end=self.end,
        )

    def cache_identity(self) -> dict[str, str]:
        return {
            "category": self.category,
            "symbol": self.symbol,
            "interval": self.interval,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class HistoricalDataResult:
    candles: tuple[Candle, ...]
    source: str
    cache_path: Path


class HistoricalCandleCache:
    def __init__(self, root: Path = Path(".cache/bybit")) -> None:
        self._root = root

    def path_for(self, request: HistoricalRequest) -> Path:
        identity = request.cache_identity()
        canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]
        filename = (
            f"{request.category}_{request.symbol}_{request.interval}_{digest}.json"
        )
        return self._root / filename

    def load(self, request: HistoricalRequest) -> tuple[Candle, ...] | None:
        path = self.path_for(request)
        if not path.exists():
            return None

        try:
            with path.open("r", encoding="utf-8") as handle:
                payload: Any = json.load(handle)
        except (OSError, ValueError):
            raise HistoricalCacheError("Historical cache is unreadable.") from None

        if not isinstance(payload, dict):
            raise HistoricalCacheError("Historical cache has an invalid format.")
        if payload.get("request") != request.cache_identity():
            raise HistoricalCacheError("Historical cache metadata does not match.")
        rows = payload.get("candles")
        if not isinstance(rows, list):
            raise HistoricalCacheError("Historical cache has an invalid format.")

        try:
            return BybitHistoricalMapper.map_rows(
                rows,
                interval=request.interval,
                start=request.start,
                effective_end=request.end,
            )
        except HistoricalDataError:
            raise HistoricalCacheError("Historical cache contains invalid candles.") from None

    def save(
        self,
        request: HistoricalRequest,
        candles: tuple[Candle, ...],
    ) -> Path:
        path = self.path_for(request)
        payload = {
            "request": request.cache_identity(),
            "candles": [
                [
                    int(candle.timestamp.timestamp() * 1000),
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.volume,
                ]
                for candle in candles
            ],
        }

        temporary_path: Path | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(payload, handle, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        except OSError:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise HistoricalCacheError("Historical cache write failed.") from None
        return path


def load_historical_data(
    *,
    client: BybitHistoricalClient,
    cache: HistoricalCandleCache,
    request: HistoricalRequest,
    refresh: bool = False,
) -> HistoricalDataResult:
    if not refresh:
        cached = cache.load(request)
        if cached is not None:
            return HistoricalDataResult(
                candles=cached,
                source="cache",
                cache_path=cache.path_for(request),
            )

    candles = client.fetch_candles(
        category=request.category,
        symbol=request.symbol,
        interval=request.interval,
        start=request.start,
        end=request.end,
    )
    cache_path = cache.save(request, candles)
    return HistoricalDataResult(
        candles=candles,
        source="Bybit",
        cache_path=cache_path,
    )
