from datetime import UTC, datetime

import pytest

from core.candle import Candle
from core.market_data import MarketData
from strategies.qtr_long.timeframe_context import (
    QTRLongTimeframeContextBuilder,
    TimeframeContextError,
)


def candle(ts: str) -> Candle:
    return Candle(
        timestamp=datetime.fromisoformat(ts).replace(tzinfo=UTC),
        open=100,
        high=101,
        low=99,
        close=100,
        volume=1,
    )


def market_data(symbol: str, timeframe: str, *timestamps: str) -> MarketData:
    return MarketData(
        symbol=symbol,
        timeframe=timeframe,
        candles=[candle(ts) for ts in timestamps],
    )


def test_builds_four_layer_context_from_only_closed_candles():
    context = QTRLongTimeframeContextBuilder().build(
        execution_5m=market_data("BTCUSDT", "5", "2025-01-01T12:00:00"),
        setup_15m=market_data("BTCUSDT", "15", "2025-01-01T11:45:00"),
        structure_1h=market_data("BTCUSDT", "60", "2025-01-01T11:00:00"),
        narrative_4h=market_data("BTCUSDT", "240", "2025-01-01T08:00:00"),
    )

    assert context.as_of == datetime(2025, 1, 1, 12, 5, tzinfo=UTC)
    assert context.execution_5m.last.timestamp == datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    assert context.setup_15m.last.timestamp == datetime(2025, 1, 1, 11, 45, tzinfo=UTC)
    assert context.structure_1h.last.timestamp == datetime(2025, 1, 1, 11, 0, tzinfo=UTC)
    assert context.narrative_4h.last.timestamp == datetime(2025, 1, 1, 8, 0, tzinfo=UTC)


def test_drops_in_progress_15m_candle():
    context = QTRLongTimeframeContextBuilder().build(
        execution_5m=market_data("BTCUSDT", "5", "2025-01-01T12:00:00"),
        setup_15m=market_data(
            "BTCUSDT",
            "15",
            "2025-01-01T11:45:00",
            "2025-01-01T12:00:00",
        ),
        structure_1h=market_data("BTCUSDT", "60", "2025-01-01T11:00:00"),
        narrative_4h=market_data("BTCUSDT", "240", "2025-01-01T08:00:00"),
    )

    assert len(context.setup_15m.candles) == 1
    assert context.setup_15m.last.timestamp == datetime(2025, 1, 1, 11, 45, tzinfo=UTC)


def test_drops_in_progress_1h_and_4h_candles():
    context = QTRLongTimeframeContextBuilder().build(
        execution_5m=market_data("BTCUSDT", "5", "2025-01-01T12:00:00"),
        setup_15m=market_data("BTCUSDT", "15", "2025-01-01T11:45:00"),
        structure_1h=market_data(
            "BTCUSDT",
            "60",
            "2025-01-01T11:00:00",
            "2025-01-01T12:00:00",
        ),
        narrative_4h=market_data(
            "BTCUSDT",
            "240",
            "2025-01-01T08:00:00",
            "2025-01-01T12:00:00",
        ),
    )

    assert context.structure_1h.last.timestamp == datetime(2025, 1, 1, 11, 0, tzinfo=UTC)
    assert context.narrative_4h.last.timestamp == datetime(2025, 1, 1, 8, 0, tzinfo=UTC)


def test_rejects_mixed_symbols():
    with pytest.raises(TimeframeContextError, match="one symbol"):
        QTRLongTimeframeContextBuilder().build(
            execution_5m=market_data("BTCUSDT", "5", "2025-01-01T12:00:00"),
            setup_15m=market_data("ETHUSDT", "15", "2025-01-01T11:45:00"),
            structure_1h=market_data("BTCUSDT", "60", "2025-01-01T11:00:00"),
            narrative_4h=market_data("BTCUSDT", "240", "2025-01-01T08:00:00"),
        )


def test_rejects_wrong_layer_timeframe():
    with pytest.raises(TimeframeContextError, match="execution_5m must use timeframe 5"):
        QTRLongTimeframeContextBuilder().build(
            execution_5m=market_data("BTCUSDT", "15", "2025-01-01T12:00:00"),
            setup_15m=market_data("BTCUSDT", "15", "2025-01-01T11:45:00"),
            structure_1h=market_data("BTCUSDT", "60", "2025-01-01T11:00:00"),
            narrative_4h=market_data("BTCUSDT", "240", "2025-01-01T08:00:00"),
        )


def test_rejects_context_when_no_closed_higher_timeframe_candle_exists():
    with pytest.raises(TimeframeContextError, match="No closed 240 candles"):
        QTRLongTimeframeContextBuilder().build(
            execution_5m=market_data("BTCUSDT", "5", "2025-01-01T12:00:00"),
            setup_15m=market_data("BTCUSDT", "15", "2025-01-01T11:45:00"),
            structure_1h=market_data("BTCUSDT", "60", "2025-01-01T11:00:00"),
            narrative_4h=market_data("BTCUSDT", "240", "2025-01-01T12:00:00"),
        )
