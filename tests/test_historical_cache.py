from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

from backtesting.historical_data import (
    HistoricalCacheError,
    HistoricalCandleCache,
    HistoricalRequest,
    load_historical_data,
)
from core.candle import Candle


START = datetime(2025, 1, 1, tzinfo=UTC)


def request() -> HistoricalRequest:
    return HistoricalRequest(
        category="linear",
        symbol="BTCUSDT",
        interval="1",
        start=START,
        end=START + timedelta(minutes=2),
    )


def candles() -> tuple[Candle, ...]:
    return tuple(
        Candle(
            timestamp=START + timedelta(minutes=index),
            open=100.0,
            high=110.0,
            low=90.0,
            close=105.0,
            volume=10.0,
            index=index,
        )
        for index in range(2)
    )


def test_cache_round_trip_and_deterministic_key(tmp_path):
    cache = HistoricalCandleCache(tmp_path)

    first_path = cache.save(request(), candles())
    loaded = cache.load(request())

    assert first_path == cache.path_for(request())
    assert loaded == candles()
    assert "BTCUSDT" in first_path.name


def test_cache_hit_performs_zero_http_calls(tmp_path):
    cache = HistoricalCandleCache(tmp_path)
    cache.save(request(), candles())
    client = Mock()

    result = load_historical_data(
        client=client,
        cache=cache,
        request=request(),
    )

    assert result.source == "cache"
    assert result.candles == candles()
    client.fetch_candles.assert_not_called()


def test_refresh_bypasses_cache_and_rewrites_it(tmp_path):
    cache = HistoricalCandleCache(tmp_path)
    cache.save(request(), candles())
    refreshed = (candles()[0],)
    client = Mock()
    client.fetch_candles.return_value = refreshed

    result = load_historical_data(
        client=client,
        cache=cache,
        request=request(),
        refresh=True,
    )

    assert result.source == "Bybit"
    assert result.candles == refreshed
    client.fetch_candles.assert_called_once()
    assert cache.load(request()) == refreshed


def test_corrupt_cache_is_rejected_without_network(tmp_path):
    cache = HistoricalCandleCache(tmp_path)
    path = cache.path_for(request())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not-json", encoding="utf-8")
    client = Mock()

    with pytest.raises(HistoricalCacheError, match="unreadable"):
        load_historical_data(client=client, cache=cache, request=request())

    client.fetch_candles.assert_not_called()
