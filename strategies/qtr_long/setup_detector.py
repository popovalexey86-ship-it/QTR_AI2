from core.analysis_context import AnalysisContext
from core.bos_type import BOSType
from core.choch_type import CHOCHType
from core.liquidity_sweep import LiquiditySweepDirection
from core.order_block import OrderBlockDirection, OrderBlockStatus
from strategies.qtr_long.setup import LongSetupCandidate, LongSetupType


class LongSetupDetector:
    """Detect the first QTR Long Genesis SMC pattern.

    Required confluence:
    - bullish liquidity sweep and reclaim;
    - bullish BOS or CHOCH confirmation;
    - active bullish Order Block;
    - current candle revisits the Order Block without invalidating it.
    """

    def __init__(self, max_sweep_age_candles: int = 20):
        if max_sweep_age_candles < 0:
            raise ValueError("max_sweep_age_candles must be >= 0")
        self._max_sweep_age_candles = max_sweep_age_candles

    def detect(self, context: AnalysisContext) -> LongSetupCandidate | None:
        sweep = context.liquidity_sweep
        order_block = context.order_block
        state = context.market_structure_state

        if sweep is None or sweep.direction != LiquiditySweepDirection.BULLISH:
            return None

        current_index = context.market_data.last.index
        if current_index >= sweep.index:
            if current_index - sweep.index > self._max_sweep_age_candles:
                return None

        if order_block is None or order_block.direction != OrderBlockDirection.BULLISH:
            return None

        if order_block.status == OrderBlockStatus.INVALIDATED:
            return None

        if state is None:
            return None

        bullish_bos = state.last_bos is not None and state.last_bos.type == BOSType.BULLISH
        bullish_choch = (
            state.last_choch is not None
            and state.last_choch.type == CHOCHType.BULLISH
        )
        if not (bullish_bos or bullish_choch):
            return None

        candle = context.market_data.last
        touches_order_block = (
            candle.low <= order_block.high and candle.high >= order_block.low
        )
        if not touches_order_block:
            return None

        # Entry uses the current reclaim/reaction close. Invalidation belongs
        # below both the bullish OB and the sweep extreme.
        entry = candle.close
        stop_loss = min(order_block.low, sweep.extreme_price)
        if stop_loss >= entry:
            return None

        return LongSetupCandidate(
            type=LongSetupType.SWEEP_RECLAIM_ORDER_BLOCK,
            liquidity_sweep=sweep,
            order_block=order_block,
            entry=entry,
            stop_loss=stop_loss,
        )
