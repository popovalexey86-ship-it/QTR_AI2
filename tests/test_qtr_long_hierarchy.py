from datetime import UTC, datetime, timedelta

import pytest

from core.analysis_context import AnalysisContext
from core.bos import BOS
from core.bos_type import BOSType
from core.candle import Candle
from core.choch import CHOCH
from core.choch_type import CHOCHType
from core.fair_value_gap import FairValueGap, FairValueGapDirection
from core.market_data import MarketData
from core.market_structure_state import MarketStructureState
from core.order_block import OrderBlock, OrderBlockDirection
from core.structure import Structure
from core.structure_type import StructureType
from core.swing import Swing
from core.swing_type import SwingType
from core.trend import Trend
from strategies.qtr_long.hierarchy import (
    LongHierarchyDecision,
    LongHierarchyResult,
    LongHierarchyStage,
    QTRLongHierarchy,
)
from strategies.qtr_long.timeframe_context import QTRLongTimeframeContext


BASE = datetime(2026, 9, 5, 8, 0, tzinfo=UTC)


def _candle(
    index: int,
    *,
    timestamp: datetime | None = None,
    open_: float = 100.0,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.5,
    volume: float = 1.0,
) -> Candle:
    return Candle(
        timestamp=timestamp or BASE + timedelta(minutes=5 * index),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        index=index,
    )


def _market_data(timeframe: str, candles: list[Candle]) -> MarketData:
    return MarketData(symbol="BTCUSDT", timeframe=timeframe, candles=candles)


def _higher_timeframe_data(timeframe: str, close: float = 100.0) -> MarketData:
    minutes = int(timeframe)
    return _market_data(
        timeframe,
        [
            _candle(
                1,
                timestamp=BASE - timedelta(minutes=minutes),
                open_=99.0,
                high=101.0,
                low=98.0,
                close=close,
            )
        ],
    )


def _swings() -> list[Swing]:
    return [
        Swing(index=1, timestamp=BASE - timedelta(hours=8), price=90.0, type=SwingType.LOW),
        Swing(index=2, timestamp=BASE - timedelta(hours=4), price=110.0, type=SwingType.HIGH),
    ]


def _setup_state(*, with_liquidity: bool = True) -> MarketStructureState:
    if not with_liquidity:
        return MarketStructureState()
    return MarketStructureState(
        last_hl=Structure(
            index=3,
            timestamp=BASE - timedelta(minutes=30),
            price=100.0,
            type=StructureType.HL,
        )
    )


def _contexts(
    execution_candles: list[Candle],
    *,
    narrative_trend: Trend = Trend.BULLISH,
    structure_trend: Trend = Trend.BULLISH,
    poi_low: float = 94.0,
    poi_high: float = 98.0,
    with_liquidity: bool = True,
    execution_state: MarketStructureState | None = None,
    execution_fvg: FairValueGap | None = None,
    execution_ob: OrderBlock | None = None,
) -> tuple[
    QTRLongTimeframeContext,
    AnalysisContext,
    AnalysisContext,
    AnalysisContext,
    AnalysisContext,
]:
    data_4h = _higher_timeframe_data("240", close=100.0)
    data_1h = _higher_timeframe_data("60", close=100.0)
    data_15m = _higher_timeframe_data("15", close=96.0)
    data_5m = _market_data("5", execution_candles)

    context_4h = AnalysisContext(
        market_data=data_4h,
        swings=_swings(),
        trend=narrative_trend,
    )
    context_1h = AnalysisContext(
        market_data=data_1h,
        trend=structure_trend,
        market_structure_state=MarketStructureState(trend=structure_trend),
    )
    context_15m = AnalysisContext(
        market_data=data_15m,
        swings=_swings(),
        market_structure_state=_setup_state(with_liquidity=with_liquidity),
        order_block=OrderBlock(
            index=4,
            timestamp=BASE - timedelta(minutes=15),
            direction=OrderBlockDirection.BULLISH,
            low=poi_low,
            high=poi_high,
        ),
    )
    context_5m = AnalysisContext(
        market_data=data_5m,
        market_structure_state=execution_state or MarketStructureState(),
        fair_value_gap=execution_fvg,
        order_block=execution_ob,
    )

    timeframe_context = QTRLongTimeframeContext(
        execution_5m=data_5m,
        setup_15m=data_15m,
        structure_1h=data_1h,
        narrative_4h=data_4h,
        as_of=data_5m.last.timestamp + timedelta(minutes=5),
    )
    return timeframe_context, context_4h, context_1h, context_15m, context_5m


def _evaluate(
    hierarchy: QTRLongHierarchy,
    contexts: tuple[
        QTRLongTimeframeContext,
        AnalysisContext,
        AnalysisContext,
        AnalysisContext,
        AnalysisContext,
    ],
) -> LongHierarchyResult:
    timeframe_context, context_4h, context_1h, context_15m, context_5m = contexts
    return hierarchy.evaluate(
        timeframe_context=timeframe_context,
        narrative_4h=context_4h,
        structure_1h=context_1h,
        setup_15m=context_15m,
        execution_5m=context_5m,
    )


def _history_before_raid() -> list[Candle]:
    return [
        _candle(index, open_=100.0, high=101.0, low=99.0, close=100.2)
        for index in range(5, 10)
    ]


def _raid_candle() -> Candle:
    return _candle(10, open_=100.5, high=102.0, low=98.5, close=101.0)


def _displacement_candle() -> Candle:
    return _candle(11, open_=101.0, high=105.0, low=100.5, close=104.5)


def test_blocks_at_4h_narrative() -> None:
    result = _evaluate(
        QTRLongHierarchy(),
        _contexts([_raid_candle()], narrative_trend=Trend.BEARISH),
    )

    assert result.decision == LongHierarchyDecision.SKIP
    assert result.stage == LongHierarchyStage.NARRATIVE_4H


def test_blocks_at_1h_structure() -> None:
    result = _evaluate(
        QTRLongHierarchy(),
        _contexts([_raid_candle()], structure_trend=Trend.BEARISH),
    )

    assert result.decision == LongHierarchyDecision.SKIP
    assert result.stage == LongHierarchyStage.STRUCTURE_1H


def test_blocks_premium_15m_poi() -> None:
    result = _evaluate(
        QTRLongHierarchy(),
        _contexts([_raid_candle()], poi_low=106.0, poi_high=108.0),
    )

    assert result.decision == LongHierarchyDecision.SKIP
    assert result.stage == LongHierarchyStage.POI_15M


def test_requires_15m_sell_side_liquidity_before_execution() -> None:
    result = _evaluate(
        QTRLongHierarchy(),
        _contexts([_raid_candle()], with_liquidity=False),
    )

    assert result.decision == LongHierarchyDecision.SKIP
    assert result.stage == LongHierarchyStage.LIQUIDITY_MAP_15M


def test_waits_for_current_5m_raid_without_scanning_old_candles() -> None:
    old_raid = _raid_candle()
    terminal = _candle(11, open_=101.0, high=103.0, low=100.5, close=102.5)
    result = _evaluate(
        QTRLongHierarchy(),
        _contexts(_history_before_raid() + [old_raid, terminal]),
    )

    assert result.decision == LongHierarchyDecision.SKIP
    assert result.stage == LongHierarchyStage.RAID_5M


def test_stateful_hierarchy_reaches_pending_buy_plan() -> None:
    hierarchy = QTRLongHierarchy()
    history = _history_before_raid()
    raid = _raid_candle()
    displacement = _displacement_candle()

    result = _evaluate(hierarchy, _contexts(history + [raid]))
    assert result.stage == LongHierarchyStage.DISPLACEMENT_5M

    result = _evaluate(hierarchy, _contexts(history + [raid, displacement]))
    assert result.stage == LongHierarchyStage.STRUCTURE_5M

    shift_state = MarketStructureState(
        last_choch=CHOCH(
            index=12,
            timestamp=BASE + timedelta(minutes=60),
            price=105.0,
            type=CHOCHType.BULLISH,
        ),
        last_bos=BOS(
            index=12,
            timestamp=BASE + timedelta(minutes=60),
            price=105.0,
            type=BOSType.BULLISH,
        ),
    )
    execution_fvg = FairValueGap(
        index=11,
        timestamp=displacement.timestamp,
        direction=FairValueGapDirection.BULLISH,
        low=101.5,
        high=103.0,
    )
    execution_ob = OrderBlock(
        index=11,
        timestamp=displacement.timestamp,
        direction=OrderBlockDirection.BULLISH,
        low=101.0,
        high=102.5,
    )
    confirmation = _candle(12, open_=104.0, high=106.0, low=103.5, close=105.0)

    result = _evaluate(
        hierarchy,
        _contexts(
            history + [raid, displacement, confirmation],
            execution_state=shift_state,
            execution_fvg=execution_fvg,
            execution_ob=execution_ob,
        ),
    )

    assert result.decision == LongHierarchyDecision.BUY_PLAN
    assert result.stage == LongHierarchyStage.READY
    assert result.entry_plan is not None
    assert result.entry_plan.entry == 102.0
    assert result.entry_plan.stop_loss == 98.5


def test_failed_higher_timeframe_gate_clears_active_5m_sequence() -> None:
    hierarchy = QTRLongHierarchy()
    history = _history_before_raid()
    raid = _raid_candle()

    first = _evaluate(hierarchy, _contexts(history + [raid]))
    assert first.stage == LongHierarchyStage.DISPLACEMENT_5M

    blocked = _evaluate(
        hierarchy,
        _contexts(history + [raid], narrative_trend=Trend.BEARISH),
    )
    assert blocked.stage == LongHierarchyStage.NARRATIVE_4H

    no_new_raid = _candle(11, open_=101.0, high=105.0, low=100.5, close=104.5)
    resumed = _evaluate(
        hierarchy,
        _contexts(history + [raid, no_new_raid]),
    )
    assert resumed.stage == LongHierarchyStage.RAID_5M


def test_rejects_analysis_not_bound_to_synchronized_context() -> None:
    hierarchy = QTRLongHierarchy()
    contexts = list(_contexts([_raid_candle()]))
    mismatched_data = _market_data("5", [_candle(99, low=90.0, close=110.0)])
    contexts[4] = AnalysisContext(market_data=mismatched_data)

    with pytest.raises(ValueError, match="execution_5m analysis"):
        _evaluate(hierarchy, tuple(contexts))  # type: ignore[arg-type]


def test_result_domain_does_not_allow_buy_without_plan() -> None:
    with pytest.raises(ValueError, match="BUY_PLAN requires an entry plan"):
        LongHierarchyResult(
            decision=LongHierarchyDecision.BUY_PLAN,
            stage=LongHierarchyStage.READY,
            reason="invalid test result",
        )
