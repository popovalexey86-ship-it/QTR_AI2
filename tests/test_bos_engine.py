from datetime import datetime

from core.bos_engine import BOSEngine
from core.bos_type import BOSType
from core.candle import Candle
from core.market_data import MarketData
from core.market_structure_state import MarketStructureState
from core.structure import Structure
from core.structure_type import StructureType


def make_structure(price: float, structure_type: StructureType) -> Structure:
    return Structure(
        index=0,
        timestamp=datetime(2025, 1, 1),
        price=price,
        type=structure_type,
    )


def make_market_data(close: float) -> MarketData:
    return MarketData(
        symbol="BTCUSDT",
        timeframe="15",
        candles=[
            Candle(
                timestamp=datetime(2025, 1, 1),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1.0,
            )
        ],
    )


def test_no_bos_when_close_equals_hh():
    state = MarketStructureState()

    state.last_hh = make_structure(100, StructureType.HH)

    engine = BOSEngine()

    assert engine.detect(state, make_market_data(100)) is None


def test_no_bos_when_close_equals_ll():
    state = MarketStructureState()

    state.last_ll = make_structure(100, StructureType.LL)

    engine = BOSEngine()

    assert engine.detect(state, make_market_data(100)) is None


def test_detect_bullish_bos():
    state = MarketStructureState()

    state.last_hh = make_structure(120, StructureType.HH)

    engine = BOSEngine()

    bos = engine.detect(state, make_market_data(121))

    assert bos is not None
    assert bos.type == BOSType.BULLISH


def test_detect_bearish_bos():
    state = MarketStructureState()

    state.last_ll = make_structure(80, StructureType.LL)

    engine = BOSEngine()

    bos = engine.detect(state, make_market_data(79))

    assert bos is not None
    assert bos.type == BOSType.BEARISH


def test_no_bullish_bos_when_close_does_not_break_hh():
    state = MarketStructureState()

    state.last_hh = make_structure(100, StructureType.HH)

    engine = BOSEngine()

    assert engine.detect(state, make_market_data(100)) is None


def test_no_bearish_bos_when_close_does_not_break_ll():
    state = MarketStructureState()

    state.last_ll = make_structure(100, StructureType.LL)

    engine = BOSEngine()

    assert engine.detect(state, make_market_data(100)) is None
