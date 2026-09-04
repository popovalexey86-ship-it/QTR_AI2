from core.bos_type import BOSType
from core.choch_type import CHOCHType
from core.fair_value_gap import FairValueGapDirection, FairValueGapStatus
from core.order_block import OrderBlockStatus
from core.trend import Trend
from strategies.qtr_long.price_location import PriceLocationEngine, PriceZone
from strategies.qtr_long.score import LongScore
from strategies.qtr_long.setup import LongSetupCandidate


class LongScoringEngine:
    """Score QTR Long Genesis candidates from 0 to 100."""

    def __init__(self, lookback: int = 20):
        if lookback < 2:
            raise ValueError("lookback must be >= 2")
        self._lookback = lookback
        self._location_engine = PriceLocationEngine(lookback=lookback)

    def score(self, context, candidate: LongSetupCandidate) -> LongScore:
        return LongScore(
            structure=self._structure_score(context),
            liquidity=self._liquidity_score(context, candidate),
            order_block=self._order_block_score(candidate),
            fvg=self._fvg_score(context, candidate),
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
        age = max(0, context.market_data.last.index - candidate.liquidity_sweep.index)
        return 20 if age <= 5 else 15

    @staticmethod
    def _order_block_score(candidate: LongSetupCandidate) -> int:
        order_block = candidate.order_block
        score = 5
        if order_block.status == OrderBlockStatus.FRESH:
            score += 5
        elif order_block.status == OrderBlockStatus.MITIGATED:
            score += 3
        if candidate.entry <= order_block.midpoint:
            score += 5
        return score

    @staticmethod
    def _fvg_score(context, candidate: LongSetupCandidate) -> int:
        gap = context.fair_value_gap
        if gap is None or gap.direction != FairValueGapDirection.BULLISH:
            return 0
        if gap.status == FairValueGapStatus.FILLED:
            return 0

        score = 5
        # Stronger confluence when bullish FVG overlaps the bullish OB.
        overlaps_ob = gap.low <= candidate.order_block.high and gap.high >= candidate.order_block.low
        if overlaps_ob:
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
            score += 4
        if (candle.close - candle.low) / candle_range >= 0.65:
            score += 3
        if body / candle_range >= 0.50:
            score += 3
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
        location = self._location_engine.evaluate(context.market_data)
        if location is None:
            return 0
        if location.zone == PriceZone.DISCOUNT:
            return 10
        if location.zone == PriceZone.EQUILIBRIUM:
            return 5
        return 0
