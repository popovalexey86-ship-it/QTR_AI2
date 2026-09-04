from core.bos import BOS
from core.bos_type import BOSType
from core.candle import Candle
from core.market_data import MarketData
from core.order_block import (
    OrderBlock,
    OrderBlockDirection,
    OrderBlockStatus,
)


class OrderBlockEngine:
    """Detect and maintain first-generation SMC order blocks.

    Detection is intentionally conservative and deterministic:
    - bullish BOS requires a bullish break candle and the last bearish candle
      before it;
    - bearish BOS mirrors that logic;
    - the break candle must close beyond the candidate candle's full range.

    More advanced displacement/FVG/liquidity confirmation belongs to later
    QTR Long scoring layers rather than this primitive detector.
    """

    def __init__(self, lookback: int = 20):
        if lookback < 1:
            raise ValueError("lookback must be >= 1")
        self._lookback = lookback

    def detect(self, market_data: MarketData, bos: BOS | None) -> OrderBlock | None:
        if bos is None or len(market_data) < 2:
            return None

        break_candle = market_data.last

        if bos.type == BOSType.BULLISH:
            if break_candle.close <= break_candle.open:
                return None
            candidate = self._find_last_opposing_candle(
                market_data,
                bullish=True,
            )
            if candidate is None or break_candle.close <= candidate.high:
                return None
            return self._build(candidate, OrderBlockDirection.BULLISH)

        if bos.type == BOSType.BEARISH:
            if break_candle.close >= break_candle.open:
                return None
            candidate = self._find_last_opposing_candle(
                market_data,
                bullish=False,
            )
            if candidate is None or break_candle.close >= candidate.low:
                return None
            return self._build(candidate, OrderBlockDirection.BEARISH)

        return None

    def update_status(self, order_block: OrderBlock, candle: Candle) -> OrderBlock:
        if order_block.status == OrderBlockStatus.INVALIDATED:
            return order_block

        if order_block.direction == OrderBlockDirection.BULLISH:
            if candle.close < order_block.low:
                return order_block.with_status(OrderBlockStatus.INVALIDATED)
        else:
            if candle.close > order_block.high:
                return order_block.with_status(OrderBlockStatus.INVALIDATED)

        touches_zone = candle.low <= order_block.high and candle.high >= order_block.low
        if touches_zone:
            return order_block.with_status(OrderBlockStatus.MITIGATED)

        return order_block

    def _find_last_opposing_candle(
        self,
        market_data: MarketData,
        *,
        bullish: bool,
    ) -> Candle | None:
        candles_before_break = market_data.candles[:-1]
        start = max(0, len(candles_before_break) - self._lookback)

        for candle in reversed(candles_before_break[start:]):
            if bullish and candle.close < candle.open:
                return candle
            if not bullish and candle.close > candle.open:
                return candle

        return None

    @staticmethod
    def _build(candle: Candle, direction: OrderBlockDirection) -> OrderBlock:
        return OrderBlock(
            index=candle.index,
            timestamp=candle.timestamp,
            direction=direction,
            low=candle.low,
            high=candle.high,
        )
