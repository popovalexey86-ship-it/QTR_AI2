from datetime import datetime

from core.analysis_engine import AnalysisEngine
from core.bos import BOS
from core.bos_type import BOSType
from core.candle import Candle
from core.market_data import MarketData
from core.order_block import OrderBlockStatus


class StubSwingEngine:
    def detect(self, market_data):
        return []


class StubStructureEngine:
    def detect(self, swings):
        return []


class StubMarketStructureEngine:
    def update(self, state, structures):
        return None


class SequencedBOSEngine:
    def __init__(self):
        self._calls = 0

    def detect(self, state, market_data):
        self._calls += 1
        if self._calls == 1:
            return BOS(
                index=1,
                timestamp=market_data.last.timestamp,
                price=100.0,
                type=BOSType.BULLISH,
            )
        return None


class StubCHOCHEngine:
    def detect(self, state, market_data):
        return None


class StubTrendEngine:
    def update(self, state):
        return None


class StubSetupEngine:
    def detect(self, state):
        return None


def make_candle(
    *,
    index: int,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> Candle:
    return Candle(
        timestamp=datetime(2025, 1, 1, 0, index),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1.0,
        index=index,
    )


def make_engine() -> AnalysisEngine:
    return AnalysisEngine(
        swing_engine=StubSwingEngine(),
        structure_engine=StubStructureEngine(),
        market_structure_engine=StubMarketStructureEngine(),
        bos_engine=SequencedBOSEngine(),
        choch_engine=StubCHOCHEngine(),
        trend_engine=StubTrendEngine(),
        setup_engine=StubSetupEngine(),
    )


def test_analysis_context_exposes_new_bullish_order_block():
    engine = make_engine()
    market_data = MarketData(
        symbol="BTCUSDT",
        timeframe="15",
        candles=[
            make_candle(index=0, open_=100, high=101, low=90, close=95),
            make_candle(index=1, open_=96, high=112, low=95, close=110),
        ],
    )

    context = engine.analyze(market_data)

    assert context.order_block is not None
    assert context.order_block.low == 90
    assert context.order_block.high == 101
    assert context.order_block.status == OrderBlockStatus.FRESH


def test_analysis_engine_tracks_order_block_mitigation_without_new_bos():
    engine = make_engine()

    first_market_data = MarketData(
        symbol="BTCUSDT",
        timeframe="15",
        candles=[
            make_candle(index=0, open_=100, high=101, low=90, close=95),
            make_candle(index=1, open_=96, high=112, low=95, close=110),
        ],
    )
    engine.analyze(first_market_data)

    second_market_data = MarketData(
        symbol="BTCUSDT",
        timeframe="15",
        candles=[
            make_candle(index=0, open_=100, high=101, low=90, close=95),
            make_candle(index=1, open_=96, high=112, low=95, close=110),
            make_candle(index=2, open_=108, high=109, low=99, close=105),
        ],
    )

    context = engine.analyze(second_market_data)

    assert context.bos is None
    assert context.order_block is not None
    assert context.order_block.status == OrderBlockStatus.MITIGATED


def test_analysis_engine_tracks_order_block_invalidation_without_new_bos():
    engine = make_engine()

    first_market_data = MarketData(
        symbol="BTCUSDT",
        timeframe="15",
        candles=[
            make_candle(index=0, open_=100, high=101, low=90, close=95),
            make_candle(index=1, open_=96, high=112, low=95, close=110),
        ],
    )
    engine.analyze(first_market_data)

    second_market_data = MarketData(
        symbol="BTCUSDT",
        timeframe="15",
        candles=[
            make_candle(index=0, open_=100, high=101, low=90, close=95),
            make_candle(index=1, open_=96, high=112, low=95, close=110),
            make_candle(index=2, open_=105, high=106, low=85, close=89),
        ],
    )

    context = engine.analyze(second_market_data)

    assert context.bos is None
    assert context.order_block is not None
    assert context.order_block.status == OrderBlockStatus.INVALIDATED
