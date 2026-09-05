from datetime import UTC, datetime, timedelta

import pytest

from core.bos import BOS
from core.bos_type import BOSType
from core.candle import Candle
from core.choch import CHOCH
from core.choch_type import CHOCHType
from core.market_data import MarketData
from core.market_structure_state import MarketStructureState
from strategies.qtr_long.displacement import LongDisplacement
from strategies.qtr_long.execution_structure import (
    LongStructureShiftEngine,
    LongStructureShiftType,
)


_BASE = datetime(2026, 1, 1, tzinfo=UTC)


def _candle(index: int) -> Candle:
    return Candle(
        timestamp=_BASE + timedelta(minutes=5 * index),
        open=100.0,
        high=104.0,
        low=99.0,
        close=103.0,
        volume=1000.0,
        index=index,
    )


def _market_data(*indices: int) -> MarketData:
    return MarketData(
        symbol="BTCUSDT",
        timeframe="5",
        candles=[_candle(index) for index in indices],
        loaded_at=_BASE + timedelta(days=1),
    )


def _displacement(index: int = 10) -> LongDisplacement:
    return LongDisplacement(
        candle=_candle(index),
        body_ratio=0.75,
        range_expansion=1.5,
        close_location=0.8,
    )


def test_bullish_choch_confirms_mss() -> None:
    state = MarketStructureState(
        last_choch=CHOCH(
            index=7,
            timestamp=_candle(11).timestamp,
            price=104.0,
            type=CHOCHType.BULLISH,
        )
    )

    result = LongStructureShiftEngine().confirm(
        state,
        _displacement(),
        _market_data(10, 11),
    )

    assert result is not None
    assert result.type == LongStructureShiftType.MSS
    assert result.index == 11
    assert result.price == 104.0


def test_bullish_bos_confirms_continuation() -> None:
    state = MarketStructureState(
        last_bos=BOS(
            index=6,
            timestamp=_candle(12).timestamp,
            price=105.0,
            type=BOSType.BULLISH,
        )
    )

    result = LongStructureShiftEngine().confirm(
        state,
        _displacement(),
        _market_data(10, 11, 12),
    )

    assert result is not None
    assert result.type == LongStructureShiftType.BOS
    assert result.index == 12


def test_bearish_structure_events_do_not_confirm_long() -> None:
    state = MarketStructureState(
        last_choch=CHOCH(
            index=7,
            timestamp=_candle(11).timestamp,
            price=98.0,
            type=CHOCHType.BEARISH,
        ),
        last_bos=BOS(
            index=6,
            timestamp=_candle(12).timestamp,
            price=97.0,
            type=BOSType.BEARISH,
        ),
    )

    assert (
        LongStructureShiftEngine().confirm(
            state,
            _displacement(),
            _market_data(10, 11, 12),
        )
        is None
    )


def test_structure_event_before_displacement_is_rejected() -> None:
    state = MarketStructureState(
        last_choch=CHOCH(
            index=8,
            timestamp=_candle(9).timestamp,
            price=103.0,
            type=CHOCHType.BULLISH,
        )
    )

    assert (
        LongStructureShiftEngine().confirm(
            state,
            _displacement(),
            _market_data(9, 10),
        )
        is None
    )


def test_structure_event_outside_execution_window_is_rejected() -> None:
    state = MarketStructureState(
        last_bos=BOS(
            index=6,
            timestamp=_candle(14).timestamp,
            price=106.0,
            type=BOSType.BULLISH,
        )
    )

    assert (
        LongStructureShiftEngine().confirm(
            state,
            _displacement(),
            _market_data(10, 11, 12, 13, 14),
        )
        is None
    )


def test_earliest_confirmation_candle_wins_and_mss_wins_same_candle_tie() -> None:
    state = MarketStructureState(
        last_choch=CHOCH(
            index=7,
            timestamp=_candle(11).timestamp,
            price=104.0,
            type=CHOCHType.BULLISH,
        ),
        last_bos=BOS(
            index=5,
            timestamp=_candle(11).timestamp,
            price=104.5,
            type=BOSType.BULLISH,
        ),
    )

    result = LongStructureShiftEngine().confirm(
        state,
        _displacement(),
        _market_data(10, 11),
    )

    assert result is not None
    assert result.type == LongStructureShiftType.MSS
    assert result.index == 11


def test_structural_reference_index_is_not_used_as_confirmation_index() -> None:
    displacement = _displacement(index=32840)
    confirmation = _candle(32840)
    state = MarketStructureState(
        last_bos=BOS(
            index=492,
            timestamp=confirmation.timestamp,
            price=66647.7,
            type=BOSType.BULLISH,
        )
    )

    result = LongStructureShiftEngine().confirm(
        state,
        displacement,
        MarketData(
            symbol="BTCUSDT",
            timeframe="5",
            candles=[confirmation],
            loaded_at=confirmation.timestamp,
        ),
    )

    assert result is not None
    assert result.type == LongStructureShiftType.BOS
    assert result.index == 32840


def test_event_timestamp_missing_from_market_data_is_rejected() -> None:
    state = MarketStructureState(
        last_choch=CHOCH(
            index=7,
            timestamp=_candle(11).timestamp,
            price=104.0,
            type=CHOCHType.BULLISH,
        )
    )

    assert (
        LongStructureShiftEngine().confirm(
            state,
            _displacement(),
            _market_data(10),
        )
        is None
    )


def test_missing_state_blocks_confirmation() -> None:
    assert (
        LongStructureShiftEngine().confirm(
            None,
            _displacement(),
            _market_data(10),
        )
        is None
    )


def test_invalid_confirmation_window_is_rejected() -> None:
    with pytest.raises(ValueError):
        LongStructureShiftEngine(max_candles_after_displacement=-1)
