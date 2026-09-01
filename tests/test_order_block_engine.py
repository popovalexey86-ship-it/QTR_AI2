from datetime import datetime, timedelta

from core.bos import BOS
from core.bos_type import BOSType
from core.candle import Candle
from core.market_data import MarketData
from core.order_block import OrderBlockDirection, OrderBlockStatus
from core.order_block_engine import OrderBlockEngine


BASE_TIME = datetime(2025, 1, 1)


def candle(
    index: int,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> Candle:
    return Candle(
        timestamp=BASE_TIME + timedelta(minutes=index),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1.0,
        index=index,
    )


def market_data(*candles: Candle) -> MarketData:
    return MarketData(symbol="BTCUSDT", timeframe="15", candles=list(candles))


def bos(bos_type: BOSType, timestamp: datetime) -> BOS:
    return BOS(index=1, timestamp=timestamp, price=100.0, type=bos_type)


def test_detect_bullish_order_block_from_last_bearish_candle():
    data = market_data(
        candle(0, 98, 99, 96, 97),
        candle(1, 100, 101, 94, 95),
        candle(2, 96, 103, 95, 102),
    )

    order_block = OrderBlockEngine().detect(
        data,
        bos(BOSType.BULLISH, data.last.timestamp),
    )

    assert order_block is not None
    assert order_block.index == 1
    assert order_block.direction == OrderBlockDirection.BULLISH
    assert order_block.low == 94
    assert order_block.high == 101
    assert order_block.status == OrderBlockStatus.FRESH


def test_detect_bearish_order_block_from_last_bullish_candle():
    data = market_data(
        candle(0, 102, 104, 101, 103),
        candle(1, 100, 106, 99, 105),
        candle(2, 104, 105, 97, 98),
    )

    order_block = OrderBlockEngine().detect(
        data,
        bos(BOSType.BEARISH, data.last.timestamp),
    )

    assert order_block is not None
    assert order_block.index == 1
    assert order_block.direction == OrderBlockDirection.BEARISH
    assert order_block.low == 99
    assert order_block.high == 106


def test_no_order_block_without_bos():
    data = market_data(
        candle(0, 100, 101, 98, 99),
        candle(1, 99, 103, 99, 102),
    )

    assert OrderBlockEngine().detect(data, None) is None


def test_no_bullish_order_block_when_break_candle_is_bearish():
    data = market_data(
        candle(0, 100, 101, 98, 99),
        candle(1, 102, 103, 97, 98),
    )

    assert (
        OrderBlockEngine().detect(
            data,
            bos(BOSType.BULLISH, data.last.timestamp),
        )
        is None
    )


def test_no_bullish_order_block_without_close_above_candidate_range():
    data = market_data(
        candle(0, 100, 105, 98, 99),
        candle(1, 99, 104, 99, 103),
    )

    assert (
        OrderBlockEngine().detect(
            data,
            bos(BOSType.BULLISH, data.last.timestamp),
        )
        is None
    )


def test_lookback_limits_candidate_search():
    data = market_data(
        candle(0, 100, 101, 98, 99),
        candle(1, 99, 100, 99, 100),
        candle(2, 100, 101, 100, 101),
        candle(3, 101, 105, 101, 104),
    )

    assert (
        OrderBlockEngine(lookback=2).detect(
            data,
            bos(BOSType.BULLISH, data.last.timestamp),
        )
        is None
    )


def test_bullish_order_block_becomes_mitigated_on_retest():
    data = market_data(
        candle(0, 100, 101, 94, 95),
        candle(1, 96, 103, 95, 102),
    )
    engine = OrderBlockEngine()
    order_block = engine.detect(data, bos(BOSType.BULLISH, data.last.timestamp))

    assert order_block is not None

    mitigated = engine.update_status(
        order_block,
        candle(2, 103, 104, 99, 102),
    )

    assert mitigated.status == OrderBlockStatus.MITIGATED


def test_bullish_order_block_becomes_invalidated_on_close_below_zone():
    data = market_data(
        candle(0, 100, 101, 94, 95),
        candle(1, 96, 103, 95, 102),
    )
    engine = OrderBlockEngine()
    order_block = engine.detect(data, bos(BOSType.BULLISH, data.last.timestamp))

    assert order_block is not None

    invalidated = engine.update_status(
        order_block,
        candle(2, 100, 101, 90, 93),
    )

    assert invalidated.status == OrderBlockStatus.INVALIDATED


def test_invalidated_order_block_cannot_return_to_mitigated():
    data = market_data(
        candle(0, 100, 101, 94, 95),
        candle(1, 96, 103, 95, 102),
    )
    engine = OrderBlockEngine()
    order_block = engine.detect(data, bos(BOSType.BULLISH, data.last.timestamp))

    assert order_block is not None

    invalidated = engine.update_status(
        order_block,
        candle(2, 100, 101, 90, 93),
    )
    unchanged = engine.update_status(
        invalidated,
        candle(3, 95, 100, 94, 99),
    )

    assert unchanged.status == OrderBlockStatus.INVALIDATED
