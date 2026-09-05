from datetime import UTC, datetime
from pathlib import Path

import pytest

from backtesting.historical_data import HistoricalDataResult
from backtesting.qtr_long_mtf_historical import (
    QTRLongHistoricalLoadRequest,
    load_qtr_long_historical_bundle,
)
from infrastructure.bybit.bybit_historical_mapper import HistoricalDataError


START = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 2, 1, tzinfo=UTC)


def test_builds_exact_four_timeframe_requests() -> None:
    request = QTRLongHistoricalLoadRequest(
        category="linear",
        symbol="BTCUSDT",
        start=START,
        end=END,
    )

    requests = request.requests()

    assert [item.interval for item in requests] == ["5", "15", "60", "240"]
    assert all(item.category == "linear" for item in requests)
    assert all(item.symbol == "BTCUSDT" for item in requests)
    assert all(item.start == START for item in requests)
    assert all(item.end == END for item in requests)


def test_loads_all_layers_in_fixed_order(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_load_historical_data(*, client, cache, request, refresh=False):
        calls.append((request.interval, refresh))
        return HistoricalDataResult(
            candles=(),
            source=request.interval,
            cache_path=Path(f"{request.interval}.json"),
        )

    monkeypatch.setattr(
        "backtesting.qtr_long_mtf_historical.load_historical_data",
        fake_load_historical_data,
    )

    request = QTRLongHistoricalLoadRequest(
        category="linear",
        symbol="BTCUSDT",
        start=START,
        end=END,
    )
    bundle = load_qtr_long_historical_bundle(
        client=object(),
        cache=object(),
        request=request,
        refresh=True,
    )

    assert calls == [("5", True), ("15", True), ("60", True), ("240", True)]
    assert bundle.category == "linear"
    assert bundle.symbol == "BTCUSDT"
    assert bundle.start == START
    assert bundle.end == END
    assert bundle.execution_5m.source == "5"
    assert bundle.setup_15m.source == "15"
    assert bundle.structure_1h.source == "60"
    assert bundle.narrative_4h.source == "240"


def test_refresh_defaults_to_false(monkeypatch: pytest.MonkeyPatch) -> None:
    refresh_values: list[bool] = []

    def fake_load_historical_data(*, client, cache, request, refresh=False):
        refresh_values.append(refresh)
        return HistoricalDataResult(
            candles=(),
            source="cache",
            cache_path=Path("cache.json"),
        )

    monkeypatch.setattr(
        "backtesting.qtr_long_mtf_historical.load_historical_data",
        fake_load_historical_data,
    )

    load_qtr_long_historical_bundle(
        client=object(),
        cache=object(),
        request=QTRLongHistoricalLoadRequest(
            category="linear",
            symbol="BTCUSDT",
            start=START,
            end=END,
        ),
    )

    assert refresh_values == [False, False, False, False]


def test_request_reuses_historical_validation() -> None:
    request = QTRLongHistoricalLoadRequest(
        category="linear",
        symbol="btcusdt",
        start=START,
        end=END,
    )

    with pytest.raises(HistoricalDataError, match="uppercase"):
        request.requests()


def test_invalid_period_is_rejected() -> None:
    request = QTRLongHistoricalLoadRequest(
        category="linear",
        symbol="BTCUSDT",
        start=END,
        end=START,
    )

    with pytest.raises(HistoricalDataError, match="earlier than end"):
        request.requests()
