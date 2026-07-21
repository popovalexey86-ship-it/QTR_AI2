from unittest.mock import Mock
from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone

import pytest

from core.market_data import MarketData
from infrastructure.bybit.bybit_collector import (
    BybitCollector,
    BybitCompletedCandleError,
)


def test_collect_returns_market_data():

    client = Mock()

    client.get_klines.return_value = {
        "result": {
            "list": [
                [
                    "1721217600000",
                    "118000",
                    "118200",
                    "117900",
                    "118100",
                    "125.37",
                    "14700000",
                ]
            ]
        }
    }

    collector = BybitCollector(client)

    market_data = collector.collect(
        category="linear",
        symbol="BTCUSDT",
        interval="1",
        limit=1,
    )
    assert market_data.symbol == "BTCUSDT"
    assert market_data.timeframe == "1"

    assert isinstance(
        market_data,
        MarketData,
    )

    assert len(market_data.candles) == 1

    assert market_data.candles[0].close == 118100.0


def _raw_candle(timestamp: datetime, close: str) -> list[str]:
    return [
        str(int(timestamp.timestamp() * 1000)),
        "100",
        "101",
        "99",
        close,
        "1",
        "100",
    ]


def test_collect_completed_excludes_forming_and_includes_exact_boundary() -> None:
    now = datetime(2026, 1, 1, 12, 30, tzinfo=UTC)
    starts = [
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        datetime(2026, 1, 1, 12, 15, tzinfo=UTC),
        datetime(2026, 1, 1, 12, 30, tzinfo=UTC),
    ]
    raw_list = [
        _raw_candle(starts[2], "103"),
        _raw_candle(starts[1], "102"),
        _raw_candle(starts[0], "101"),
    ]
    original = deepcopy(raw_list)
    client = Mock()
    client.get_klines.return_value = {"result": {"list": raw_list}}
    clock = Mock(return_value=now)
    collector = BybitCollector(client, interval="15", clock=clock)

    market_data = collector.collect_completed()

    assert [item.timestamp for item in market_data.candles] == starts[:2]
    assert [item.close for item in market_data.candles] == [101.0, 102.0]
    assert raw_list == original
    clock.assert_called_once_with()


def test_collect_completed_fails_when_only_forming_candles_remain() -> None:
    start = datetime(2026, 1, 1, 12, 30, tzinfo=UTC)
    client = Mock()
    client.get_klines.return_value = {
        "result": {"list": [_raw_candle(start, "100")]}
    }
    collector = BybitCollector(
        client,
        interval="15",
        clock=lambda: start + timedelta(minutes=14, seconds=59),
    )

    with pytest.raises(BybitCompletedCandleError, match="no completed"):
        collector.collect_completed()


@pytest.mark.parametrize("interval", ["D", "W", "M", "1h", "0", "-15"])
def test_collect_completed_rejects_unsupported_live_interval(interval: str) -> None:
    client = Mock()
    collector = BybitCollector(
        client,
        interval=interval,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )

    with pytest.raises(BybitCompletedCandleError, match="Unsupported"):
        collector.collect_completed()

    client.get_klines.assert_not_called()


@pytest.mark.parametrize(
    "now",
    [
        datetime(2026, 1, 1),
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=3),
    ],
)
def test_collect_completed_requires_utc_clock(now: datetime) -> None:
    if now.tzinfo is not None:
        now = now.replace(tzinfo=timezone(timedelta(hours=3)))
    client = Mock()
    collector = BybitCollector(client, interval="15", clock=lambda: now)

    with pytest.raises(BybitCompletedCandleError, match="UTC"):
        collector.collect_completed()

    client.get_klines.assert_not_called()
