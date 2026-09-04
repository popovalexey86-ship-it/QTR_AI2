from datetime import UTC, datetime, timedelta

import pytest

from core.candle import Candle
from core.market_data import MarketData
from core.structure_type import StructureType
from strategies.qtr_long.displacement import LongDisplacementEngine
from strategies.qtr_long.execution_raid import LongLiquidityRaid
from strategies.qtr_long.liquidity_map import SellSideLiquidityLevel


BASE = datetime(2026, 1, 1, tzinfo=UTC)


def candle(
    index: int,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> Candle:
    return Candle(
        index=index,
        timestamp=BASE + timedelta(minutes=5 * index),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=100.0,
    )


def market(*candles: Candle) -> MarketData:
    return MarketData(symbol="BTCUSDT", timeframe="5", candles=list(candles))


def raid(raid_candle: Candle) -> LongLiquidityRaid:
    level = SellSideLiquidityLevel(
        price=99.0,
        source_index=1,
        source_timestamp=BASE,
        source_type=StructureType.HL,
    )
    return LongLiquidityRaid(level=level, candle=raid_candle)


def baseline_with(candidate: Candle, *, extras: tuple[Candle, ...] = ()) -> MarketData:
    candles = (
        candle(0, 100.0, 100.5, 99.5, 100.1),
        candle(1, 100.1, 100.6, 99.6, 100.0),
        candle(2, 100.0, 100.5, 99.5, 100.1),
        candle(3, 100.1, 100.6, 99.6, 100.0),
        candle(4, 100.0, 100.5, 99.5, 100.1),
        candle(5, 99.4, 100.2, 98.5, 99.6),
        candidate,
        *extras,
    )
    return market(*candles)


def test_detects_bullish_displacement_after_raid() -> None:
    raid_candle = candle(5, 99.4, 100.2, 98.5, 99.6)
    displacement_candle = candle(6, 99.6, 101.6, 99.5, 101.3)

    result = LongDisplacementEngine().detect(
        baseline_with(displacement_candle),
        raid(raid_candle),
    )

    assert result is not None
    assert result.candle == displacement_candle
    assert result.body_ratio >= 0.60
    assert result.range_expansion >= 1.20
    assert result.close_location >= 0.75


def test_rejects_bearish_candle() -> None:
    raid_candle = candle(5, 99.4, 100.2, 98.5, 99.6)
    candidate = candle(6, 101.2, 101.5, 99.0, 99.4)

    assert LongDisplacementEngine().detect(baseline_with(candidate), raid(raid_candle)) is None


def test_rejects_weak_body() -> None:
    raid_candle = candle(5, 99.4, 100.2, 98.5, 99.6)
    candidate = candle(6, 100.0, 102.0, 99.0, 100.6)

    assert LongDisplacementEngine().detect(baseline_with(candidate), raid(raid_candle)) is None


def test_rejects_insufficient_range_expansion() -> None:
    raid_candle = candle(5, 99.4, 100.2, 98.5, 99.6)
    candidate = candle(6, 99.6, 100.5, 99.5, 100.4)

    assert LongDisplacementEngine().detect(baseline_with(candidate), raid(raid_candle)) is None


def test_rejects_close_too_far_from_high() -> None:
    raid_candle = candle(5, 99.4, 100.2, 98.5, 99.6)
    candidate = candle(6, 99.0, 102.0, 98.5, 100.7)

    assert LongDisplacementEngine().detect(baseline_with(candidate), raid(raid_candle)) is None


def test_rejects_close_that_does_not_advance_beyond_raid_reclaim() -> None:
    raid_candle = candle(5, 99.4, 100.2, 98.5, 101.0)
    candidate = candle(6, 99.0, 101.2, 98.8, 100.9)

    assert LongDisplacementEngine().detect(baseline_with(candidate), raid(raid_candle)) is None


def test_ignores_displacement_after_execution_window() -> None:
    raid_candle = candle(5, 99.4, 100.2, 98.5, 99.6)
    weak_6 = candle(6, 99.6, 100.5, 99.5, 100.1)
    weak_7 = candle(7, 100.1, 100.6, 99.8, 100.2)
    weak_8 = candle(8, 100.2, 100.7, 99.9, 100.3)
    strong_9 = candle(9, 100.3, 102.4, 100.2, 102.2)

    data = baseline_with(weak_6, extras=(weak_7, weak_8, strong_9))

    assert LongDisplacementEngine().detect(data, raid(raid_candle)) is None


def test_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError):
        LongDisplacementEngine(max_candles_after_raid=0)
    with pytest.raises(ValueError):
        LongDisplacementEngine(lookback=0)
    with pytest.raises(ValueError):
        LongDisplacementEngine(minimum_body_ratio=0)
