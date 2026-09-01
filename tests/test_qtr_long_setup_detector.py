from datetime import datetime

from core.analysis_context import AnalysisContext
from core.bos import BOS
from core.bos_type import BOSType
from core.candle import Candle
from core.liquidity_sweep import LiquiditySweep, LiquiditySweepDirection
from core.market_data import MarketData
from core.market_structure_state import MarketStructureState
from core.order_block import OrderBlock, OrderBlockDirection, OrderBlockStatus
from strategies.qtr_long.setup import LongSetupType
from strategies.qtr_long.setup_detector import LongSetupDetector


def make_context() -> AnalysisContext:
    market_data = MarketData(
        symbol="BTCUSDT",
        timeframe="15",
        candles=[
            Candle(
                index=12,
                timestamp=datetime(2025, 1, 1),
                open=99,
                high=102,
                low=97.5,
                close=101,
                volume=2,
            )
        ],
    )
    state = MarketStructureState()
    state.last_bos = BOS(
        index=10,
        timestamp=datetime(2025, 1, 1),
        price=100,
        type=BOSType.BULLISH,
    )

    context = AnalysisContext(
        market_data=market_data,
        market_structure_state=state,
    )
    context.liquidity_sweep = LiquiditySweep(
        index=11,
        timestamp=datetime(2025, 1, 1),
        direction=LiquiditySweepDirection.BULLISH,
        swept_price=98,
        extreme_price=96.5,
        reclaim_close=99,
    )
    context.order_block = OrderBlock(
        index=9,
        timestamp=datetime(2025, 1, 1),
        direction=OrderBlockDirection.BULLISH,
        low=97,
        high=100,
        status=OrderBlockStatus.MITIGATED,
    )
    return context


def test_detects_sweep_reclaim_order_block_long_candidate():
    candidate = LongSetupDetector().detect(make_context())

    assert candidate is not None
    assert candidate.type == LongSetupType.SWEEP_RECLAIM_ORDER_BLOCK
    assert candidate.entry == 101
    assert candidate.stop_loss == 96.5


def test_rejects_candidate_without_bullish_structure_confirmation():
    context = make_context()
    context.market_structure_state.last_bos = None

    assert LongSetupDetector().detect(context) is None


def test_rejects_bearish_order_block():
    context = make_context()
    context.order_block = OrderBlock(
        index=9,
        timestamp=datetime(2025, 1, 1),
        direction=OrderBlockDirection.BEARISH,
        low=97,
        high=100,
    )

    assert LongSetupDetector().detect(context) is None


def test_rejects_when_price_has_not_returned_to_order_block():
    context = make_context()
    context.market_data.candles[0] = Candle(
        index=12,
        timestamp=datetime(2025, 1, 1),
        open=103,
        high=105,
        low=102,
        close=104,
        volume=2,
    )

    assert LongSetupDetector().detect(context) is None
