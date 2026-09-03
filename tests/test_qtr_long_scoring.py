from datetime import datetime, timedelta

from core.analysis_context import AnalysisContext
from core.bos import BOS
from core.bos_type import BOSType
from core.candle import Candle
from core.choch import CHOCH
from core.choch_type import CHOCHType
from core.liquidity_sweep import LiquiditySweep, LiquiditySweepDirection
from core.market_data import MarketData
from core.market_structure_state import MarketStructureState
from core.order_block import OrderBlock, OrderBlockDirection, OrderBlockStatus
from core.trend import Trend
from strategies.qtr_long.scoring import LongScoringEngine
from strategies.qtr_long.setup import LongSetupCandidate, LongSetupType


def build_context() -> tuple[AnalysisContext, LongSetupCandidate]:
    start = datetime(2026, 1, 1)
    candles = []
    for index in range(20):
        candles.append(
            Candle(
                index=index,
                timestamp=start + timedelta(minutes=15 * index),
                open=100,
                high=110 if index == 0 else 103,
                low=90 if index == 1 else 97,
                close=100,
                volume=100,
            )
        )

    candles.append(
        Candle(
            index=20,
            timestamp=start + timedelta(minutes=15 * 20),
            open=95.2,
            high=97.0,
            low=95.0,
            close=96.5,
            volume=200,
        )
    )
    market_data = MarketData(symbol="BTCUSDT", timeframe="15", candles=candles)

    state = MarketStructureState(trend=Trend.BULLISH)
    state.last_bos = BOS(
        index=19,
        timestamp=candles[19].timestamp,
        price=101,
        type=BOSType.BULLISH,
    )
    state.last_choch = CHOCH(
        index=18,
        timestamp=candles[18].timestamp,
        price=100,
        type=CHOCHType.BULLISH,
    )

    context = AnalysisContext(market_data=market_data)
    context.trend = Trend.BULLISH
    context.market_structure_state = state

    sweep = LiquiditySweep(
        index=18,
        timestamp=candles[18].timestamp,
        direction=LiquiditySweepDirection.BULLISH,
        swept_price=91,
        extreme_price=89.5,
        reclaim_close=92,
    )
    order_block = OrderBlock(
        index=17,
        timestamp=candles[17].timestamp,
        direction=OrderBlockDirection.BULLISH,
        low=94,
        high=100,
        status=OrderBlockStatus.FRESH,
    )
    candidate = LongSetupCandidate(
        type=LongSetupType.SWEEP_RECLAIM_ORDER_BLOCK,
        liquidity_sweep=sweep,
        order_block=order_block,
        entry=96.5,
        stop_loss=89.5,
    )
    return context, candidate


def test_strong_confluence_can_score_100():
    context, candidate = build_context()

    score = LongScoringEngine().score(context, candidate)

    assert score.structure == 25
    assert score.liquidity == 20
    assert score.order_block == 20
    assert score.momentum == 15
    assert score.volume == 10
    assert score.location == 10
    assert score.total == 100


def test_mitigated_order_block_scores_less_than_fresh():
    context, candidate = build_context()
    mitigated = OrderBlock(
        index=candidate.order_block.index,
        timestamp=candidate.order_block.timestamp,
        direction=candidate.order_block.direction,
        low=candidate.order_block.low,
        high=candidate.order_block.high,
        status=OrderBlockStatus.MITIGATED,
    )
    candidate = LongSetupCandidate(
        type=candidate.type,
        liquidity_sweep=candidate.liquidity_sweep,
        order_block=mitigated,
        entry=candidate.entry,
        stop_loss=candidate.stop_loss,
    )

    score = LongScoringEngine().score(context, candidate)

    assert score.order_block == 17


def test_old_sweep_loses_recency_bonus():
    context, candidate = build_context()
    old_sweep = LiquiditySweep(
        index=10,
        timestamp=context.market_data.candles[10].timestamp,
        direction=LiquiditySweepDirection.BULLISH,
        swept_price=91,
        extreme_price=89.5,
        reclaim_close=92,
    )
    candidate = LongSetupCandidate(
        type=candidate.type,
        liquidity_sweep=old_sweep,
        order_block=candidate.order_block,
        entry=candidate.entry,
        stop_loss=candidate.stop_loss,
    )

    score = LongScoringEngine().score(context, candidate)

    assert score.liquidity == 15


def test_weak_volume_gets_no_volume_points():
    context, candidate = build_context()
    last = context.market_data.candles[-1]
    context.market_data.candles[-1] = Candle(
        index=last.index,
        timestamp=last.timestamp,
        open=last.open,
        high=last.high,
        low=last.low,
        close=last.close,
        volume=50,
    )

    score = LongScoringEngine().score(context, candidate)

    assert score.volume == 0
