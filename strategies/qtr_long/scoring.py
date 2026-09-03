from core.bos_type import BOSType
from core.choch_type import CHOCHType
from core.order_block import OrderBlockStatus
from core.trend import Trend
from strategies.qtr_long.score import LongScore
from strategies.qtr_long.setup import LongSetupCandidate


class LongScoringEngine:
    """Score QTR Long Genesis candidates from 0 to 100.

    The score is intentionally decomposed into observable components so later
    backtests can recalibrate weights without hiding the reason for a signal.
    """

    def __init__(self, lookback: int = 20):
        if lookback < 2:
            raise ValueError("lookback must be >= 2")
        self._lookback = lookback

    def score(self, context, candidate: LongSetupCandidate) -> LongScore:
        return LongScore(
            structure=self._structure_score(context),
            liquidity=self._liquidity_score(context, candidate),
            order_block=self._order_block_score(context, candidate),
            momentum=self._momentum_score(context),
            volume=self._volume_score(context),
            location=self._location_score(context),
        )

    @staticmethod
    def _structure_score(context) -> int:
        score = 0
        if context.trend == Trend.BULLISH:
            score += 10

        state = context.market_structure_state
        if state is None:
            return score

        if state.last_choch is not None and state.last_choch.type == CHOCHType.BULLISH:
            score += 10
        if state.last_bos is not None and state.last_bos.type == BOSType.BULLISH:
            score += 5
        return score

    @staticmethod
    def _liquidity_score(context, candidate: LongSetupCandidate) -> int:
        sweep = candidate.liquidity_sweep
        current_index = context.market_data.last.index
        age = max(0, current_index - sweep.index)

        score = 15  # bullish sweep + reclaim are mandatory for this setup family
        if age <= 5:
            score += 5
        return score

    @staticmethod
    def _order_block_score(context, candidate: LongSetupCandidate) -> int:
        order_block = candidate.order_block
        score = 8  # bullish OB is mandatory for this setup family

        if order_block.status == OrderBlockStatus.FRESH:
            score += 7
        elif order_block.status == OrderBlockStatus.MITIGATED:
            score += 4

        if candidate.entry <= order_block.midpoint:
            score += 5
        return score

    @staticmethod
    def _momentum_score(context) -> int:
        candle = context.market_data.last
        candle_range = candle.high - candle.low
        if candle_range <= 0:
            return 0

        score = 0
        body = candle.close - candle.open
        if body > 0:
            score += 5
        if (candle.close - candle.low) / candle_range >= 0.65:
            score += 5
        if body / candle_range >= 0.50:
            score += 5
        return score

    def _volume_score(self, context) -> int:
        candles = context.market_data.candles
        if len(candles) < 2:
            return 0

        previous = candles[max(0, len(candles) - self._lookback - 1):-1]
        if not previous:
            return 0

        average = sum(candle.volume for candle in previous) / len(previous)
        if average <= 0:
            return 0

        ratio = candles[-1].volume / average
        if ratio >= 1.5:
            return 10
        if ratio >= 1.0:
            return 5
        return 0

    def _location_score(self, context) -> int:
        candles = context.market_data.candles[-self._lookback:]
        if len(candles) < 2:
            return 0

        low = min(candle.low for candle in candles)
        high = max(candle.high for candle in candles)
        width = high - low
        if width <= 0:
            return 0

        position = (context.market_data.last.close - low) / width
        if position <= 0.50:
            return 10
        if position <= 0.65:
            return 5
        return 0
