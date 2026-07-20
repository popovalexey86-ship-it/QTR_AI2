from datetime import datetime

from core.candle import Candle
from core.choch_engine import CHOCHEngine
from core.choch_type import CHOCHType
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


def test_no_bearish_choch_when_close_equals_hl():
    state = MarketStructureState()

    state.last_hl = make_structure(100, StructureType.HL)

    engine = CHOCHEngine()

    assert engine.detect(state, make_market_data(100)) is None


def test_no_bullish_choch_when_close_equals_lh():
    state = MarketStructureState()

    state.last_lh = make_structure(100, StructureType.LH)

    engine = CHOCHEngine()

    assert engine.detect(state, make_market_data(100)) is None


def test_detect_bearish_choch():
    state = MarketStructureState()

    state.last_hl = make_structure(80, StructureType.HL)

    engine = CHOCHEngine()

    choch = engine.detect(state, make_market_data(79))

    assert choch is not None
    assert choch.type == CHOCHType.BEARISH
    assert choch.price == 80


def test_detect_bullish_choch():
    state = MarketStructureState()

    state.last_lh = make_structure(120, StructureType.LH)

    engine = CHOCHEngine()

    choch = engine.detect(state, make_market_data(121))

    assert choch is not None
    assert choch.type == CHOCHType.BULLISH
    assert choch.price == 120


def test_no_bearish_choch_when_close_does_not_break_hl():
    state = MarketStructureState()

    state.last_hl = make_structure(100, StructureType.HL)

    engine = CHOCHEngine()

    assert engine.detect(state, make_market_data(100)) is None


def test_no_bullish_choch_when_close_does_not_break_lh():
    state = MarketStructureState()

    state.last_lh = make_structure(100, StructureType.LH)

    engine = CHOCHEngine()

    assert engine.detect(state, make_market_data(100)) is None
