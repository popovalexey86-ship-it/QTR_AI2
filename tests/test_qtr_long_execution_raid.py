from datetime import UTC, datetime

from core.candle import Candle
from core.structure_type import StructureType
from strategies.qtr_long.execution_raid import LongLiquidityRaidDetector
from strategies.qtr_long.liquidity_map import LongLiquidityMap, SellSideLiquidityLevel


def _level(price: float, index: int = 1) -> SellSideLiquidityLevel:
    return SellSideLiquidityLevel(
        price=price,
        source_index=index,
        source_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        source_type=StructureType.HL,
    )


def _candle(*, low: float, close: float, high: float = 110.0, open_: float = 105.0) -> Candle:
    return Candle(
        timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1.0,
        index=10,
    )


def test_detects_sweep_and_reclaim_of_sell_side_liquidity() -> None:
    liquidity_map = LongLiquidityMap(sell_side=(_level(100.0),))

    raid = LongLiquidityRaidDetector().detect(
        _candle(low=99.0, close=101.0),
        liquidity_map,
    )

    assert raid is not None
    assert raid.level.price == 100.0
    assert raid.extreme_price == 99.0
    assert raid.reclaim_close == 101.0


def test_touch_without_trade_below_level_is_not_a_raid() -> None:
    liquidity_map = LongLiquidityMap(sell_side=(_level(100.0),))

    raid = LongLiquidityRaidDetector().detect(
        _candle(low=100.0, close=101.0),
        liquidity_map,
    )

    assert raid is None


def test_close_on_level_is_not_a_reclaim() -> None:
    liquidity_map = LongLiquidityMap(sell_side=(_level(100.0),))

    raid = LongLiquidityRaidDetector().detect(
        _candle(low=99.0, close=100.0),
        liquidity_map,
    )

    assert raid is None


def test_sweep_without_reclaim_is_not_a_long_raid() -> None:
    liquidity_map = LongLiquidityMap(sell_side=(_level(100.0),))

    raid = LongLiquidityRaidDetector().detect(
        _candle(low=98.0, close=99.5),
        liquidity_map,
    )

    assert raid is None


def test_multiple_reclaimed_levels_anchor_to_highest_level() -> None:
    liquidity_map = LongLiquidityMap(
        sell_side=(_level(98.0, 1), _level(100.0, 2), _level(102.0, 3))
    )

    raid = LongLiquidityRaidDetector().detect(
        _candle(low=97.0, close=103.0),
        liquidity_map,
    )

    assert raid is not None
    assert raid.level.price == 102.0
