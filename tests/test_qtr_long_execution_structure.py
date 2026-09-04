from datetime import UTC, datetime

import pytest

from core.bos import BOS
from core.bos_type import BOSType
from core.candle import Candle
from core.choch import CHOCH
from core.choch_type import CHOCHType
from core.market_structure_state import MarketStructureState
from strategies.qtr_long.displacement import LongDisplacement
from strategies.qtr_long.execution_structure import (
    LongStructureShiftEngine,
    LongStructureShiftType,
)


def _candle(index: int) -> Candle:
    return Candle(
        timestamp=datetime(2026, 1, 1, 0, index, tzinfo=UTC),
        open=100.0,
        high=104.0,
        low=99.0,
        close=103.0,
        volume=1000.0,
        index=index,
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
            index=11,
            timestamp=datetime(2026, 1, 1, 0, 11, tzinfo=UTC),
            price=104.0,
            type=CHOCHType.BULLISH,
        )
    )

    result = LongStructureShiftEngine().confirm(state, _displacement())

    assert result is not None
    assert result.type == LongStructureShiftType.MSS
    assert result.index == 11
    assert result.price == 104.0


def test_bullish_bos_confirms_continuation() -> None:
    state = MarketStructureState(
        last_bos=BOS(
            index=12,
            timestamp=datetime(2026, 1, 1, 0, 12, tzinfo=UTC),
            price=105.0,
            type=BOSType.BULLISH,
        )
    )

    result = LongStructureShiftEngine().confirm(state, _displacement())

    assert result is not None
    assert result.type == LongStructureShiftType.BOS
    assert result.index == 12


def test_bearish_structure_events_do_not_confirm_long() -> None:
    state = MarketStructureState(
        last_choch=CHOCH(
            index=11,
            timestamp=datetime(2026, 1, 1, 0, 11, tzinfo=UTC),
            price=98.0,
            type=CHOCHType.BEARISH,
        ),
        last_bos=BOS(
            index=12,
            timestamp=datetime(2026, 1, 1, 0, 12, tzinfo=UTC),
            price=97.0,
            type=BOSType.BEARISH,
        ),
    )

    assert LongStructureShiftEngine().confirm(state, _displacement()) is None


def test_structure_event_before_displacement_is_rejected() -> None:
    state = MarketStructureState(
        last_choch=CHOCH(
            index=9,
            timestamp=datetime(2026, 1, 1, 0, 9, tzinfo=UTC),
            price=103.0,
            type=CHOCHType.BULLISH,
        )
    )

    assert LongStructureShiftEngine().confirm(state, _displacement()) is None


def test_structure_event_outside_execution_window_is_rejected() -> None:
    state = MarketStructureState(
        last_bos=BOS(
            index=14,
            timestamp=datetime(2026, 1, 1, 0, 14, tzinfo=UTC),
            price=106.0,
            type=BOSType.BULLISH,
        )
    )

    assert LongStructureShiftEngine().confirm(state, _displacement()) is None


def test_earliest_valid_event_wins_and_mss_wins_same_index_tie() -> None:
    state = MarketStructureState(
        last_choch=CHOCH(
            index=11,
            timestamp=datetime(2026, 1, 1, 0, 11, tzinfo=UTC),
            price=104.0,
            type=CHOCHType.BULLISH,
        ),
        last_bos=BOS(
            index=11,
            timestamp=datetime(2026, 1, 1, 0, 11, tzinfo=UTC),
            price=104.5,
            type=BOSType.BULLISH,
        ),
    )

    result = LongStructureShiftEngine().confirm(state, _displacement())

    assert result is not None
    assert result.type == LongStructureShiftType.MSS


def test_missing_state_blocks_confirmation() -> None:
    assert LongStructureShiftEngine().confirm(None, _displacement()) is None


def test_invalid_confirmation_window_is_rejected() -> None:
    with pytest.raises(ValueError):
        LongStructureShiftEngine(max_candles_after_displacement=-1)
