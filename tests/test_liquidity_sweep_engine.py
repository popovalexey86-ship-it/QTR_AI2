from datetime import datetime

from core.candle import Candle
from core.liquidity_sweep import LiquiditySweepDirection
from core.liquidity_sweep_engine import LiquiditySweepEngine
from core.market_data import MarketData
from core.market_structure_state import MarketStructureState
from core.structure import Structure
from core.structure_type import StructureType


def structure(index: int, price: float, kind: StructureType) -> Structure:
    return Structure(
        index=index,
        timestamp=datetime(2025, 1, 1),
        price=price,
        type=kind,
    )


def market_data(*, high: float, low: float, close: float) -> MarketData:
    return MarketData(
        symbol="BTCUSDT",
        timeframe="15",
        candles=[
            Candle(
                index=10,
                timestamp=datetime(2025, 1, 1),
                open=100,
                high=high,
                low=low,
                close=close,
                volume=1,
            )
        ],
    )


def test_detects_bullish_sweep_and_reclaim_of_latest_low():
    state = MarketStructureState()
    state.last_ll = structure(3, 95, StructureType.LL)
    state.last_hl = structure(8, 98, StructureType.HL)

    sweep = LiquiditySweepEngine().detect(
        state,
        market_data(high=103, low=97, close=99),
    )

    assert sweep is not None
    assert sweep.direction == LiquiditySweepDirection.BULLISH
    assert sweep.swept_price == 98
    assert sweep.extreme_price == 97
    assert sweep.reclaim_close == 99


def test_does_not_detect_bullish_sweep_without_reclaim_close():
    state = MarketStructureState()
    state.last_hl = structure(8, 98, StructureType.HL)

    sweep = LiquiditySweepEngine().detect(
        state,
        market_data(high=103, low=97, close=98),
    )

    assert sweep is None


def test_detects_bearish_sweep_symmetrically():
    state = MarketStructureState()
    state.last_lh = structure(8, 102, StructureType.LH)

    sweep = LiquiditySweepEngine().detect(
        state,
        market_data(high=103, low=97, close=101),
    )

    assert sweep is not None
    assert sweep.direction == LiquiditySweepDirection.BEARISH
    assert sweep.swept_price == 102
