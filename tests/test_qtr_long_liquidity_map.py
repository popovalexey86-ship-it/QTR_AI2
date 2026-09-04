from datetime import UTC, datetime

from core.market_structure_state import MarketStructureState
from core.structure import Structure
from core.structure_type import StructureType
from strategies.qtr_long.liquidity_map import LongLiquidityMapEngine


def _structure(index: int, price: float, type_: StructureType) -> Structure:
    return Structure(
        index=index,
        timestamp=datetime(2026, 1, 1, index % 24, tzinfo=UTC),
        price=price,
        type=type_,
    )


def test_missing_structure_produces_empty_liquidity_map() -> None:
    result = LongLiquidityMapEngine().build(None)

    assert result.sell_side == ()
    assert result.has_sell_side_liquidity is False


def test_map_uses_confirmed_hl_and_ll_levels() -> None:
    state = MarketStructureState(
        last_hl=_structure(10, 100.0, StructureType.HL),
        last_ll=_structure(12, 95.0, StructureType.LL),
    )

    result = LongLiquidityMapEngine().build(state)

    assert [level.price for level in result.sell_side] == [95.0, 100.0]
    assert result.has_sell_side_liquidity is True


def test_map_includes_previous_confirmed_sell_side_levels() -> None:
    state = MarketStructureState(
        previous_hl=_structure(3, 101.0, StructureType.HL),
        last_hl=_structure(7, 103.0, StructureType.HL),
        previous_ll=_structure(4, 94.0, StructureType.LL),
        last_ll=_structure(8, 96.0, StructureType.LL),
    )

    result = LongLiquidityMapEngine().build(state)

    assert [level.source_index for level in result.sell_side] == [8, 7, 4, 3]


def test_duplicate_price_keeps_latest_confirmed_level() -> None:
    state = MarketStructureState(
        previous_hl=_structure(2, 100.0, StructureType.HL),
        last_ll=_structure(9, 100.0, StructureType.LL),
    )

    result = LongLiquidityMapEngine().build(state)

    assert len(result.sell_side) == 1
    assert result.sell_side[0].source_index == 9
    assert result.sell_side[0].source_type == StructureType.LL


def test_map_does_not_use_high_side_structure() -> None:
    state = MarketStructureState(
        last_hh=_structure(5, 120.0, StructureType.HH),
        last_lh=_structure(6, 115.0, StructureType.LH),
    )

    result = LongLiquidityMapEngine().build(state)

    assert result.sell_side == ()
