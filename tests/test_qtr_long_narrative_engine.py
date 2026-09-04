from datetime import datetime

import pytest

from core.analysis_context import AnalysisContext
from core.candle import Candle
from core.market_data import MarketData
from core.swing import Swing
from core.swing_type import SwingType
from core.trend import Trend
from strategies.qtr_long.narrative import LongNarrativeBias
from strategies.qtr_long.narrative_engine import LongNarrativeEngine


def make_context(*, trend: Trend | None, close: float, timeframe: str = "240") -> AnalysisContext:
    market_data = MarketData(
        symbol="BTCUSDT",
        timeframe=timeframe,
        candles=[
            Candle(
                timestamp=datetime(2025, 1, 1),
                open=close,
                high=close + 1,
                low=close - 1,
                close=close,
                volume=1,
            )
        ],
    )
    context = AnalysisContext(market_data=market_data)
    context.trend = trend
    context.swings = [
        Swing(
            index=1,
            timestamp=datetime(2024, 12, 1),
            price=100,
            type=SwingType.LOW,
        ),
        Swing(
            index=2,
            timestamp=datetime(2024, 12, 15),
            price=200,
            type=SwingType.HIGH,
        ),
    ]
    return context


def test_bullish_structure_in_discount_creates_bullish_narrative():
    narrative = LongNarrativeEngine().evaluate(
        make_context(trend=Trend.BULLISH, close=125)
    )

    assert narrative.bias == LongNarrativeBias.BULLISH
    assert "discount" in narrative.reason


def test_bullish_structure_near_equilibrium_creates_bullish_narrative():
    narrative = LongNarrativeEngine().evaluate(
        make_context(trend=Trend.BULLISH, close=150)
    )

    assert narrative.bias == LongNarrativeBias.BULLISH
    assert "equilibrium" in narrative.reason


def test_bullish_structure_in_premium_is_neutral_not_buy_permission():
    narrative = LongNarrativeEngine().evaluate(
        make_context(trend=Trend.BULLISH, close=180)
    )

    assert narrative.bias == LongNarrativeBias.NEUTRAL
    assert "premium" in narrative.reason


def test_bearish_structure_is_bearish_narrative_even_in_discount():
    narrative = LongNarrativeEngine().evaluate(
        make_context(trend=Trend.BEARISH, close=125)
    )

    assert narrative.bias == LongNarrativeBias.BEARISH


def test_range_structure_is_neutral():
    narrative = LongNarrativeEngine().evaluate(
        make_context(trend=Trend.RANGE, close=125)
    )

    assert narrative.bias == LongNarrativeBias.NEUTRAL


def test_missing_confirmed_dealing_range_is_neutral():
    context = make_context(trend=Trend.BULLISH, close=125)
    context.swings = []

    narrative = LongNarrativeEngine().evaluate(context)

    assert narrative.bias == LongNarrativeBias.NEUTRAL
    assert "unavailable" in narrative.reason


def test_non_4h_context_is_rejected():
    with pytest.raises(ValueError, match="4H"):
        LongNarrativeEngine().evaluate(
            make_context(trend=Trend.BULLISH, close=125, timeframe="60")
        )
