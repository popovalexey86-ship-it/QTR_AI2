from dataclasses import dataclass
from datetime import datetime

from strategies.qtr_long.score import LongScore
from strategies.qtr_long.setup import LongSetupCandidate


@dataclass(frozen=True, slots=True)
class LongSignalDiagnostic:
    """Immutable snapshot of an accepted QTR Long signal before execution."""

    signal_timestamp: datetime
    setup_type: str
    score_total: int
    score_grade: str
    score_structure: int
    score_liquidity: int
    score_order_block: int
    score_fvg: int
    score_momentum: int
    score_volume: int
    score_location: int
    sweep_timestamp: datetime
    sweep_price: float
    sweep_extreme: float
    sweep_reclaim_close: float
    order_block_timestamp: datetime
    order_block_status: str
    order_block_low: float
    order_block_high: float
    order_block_midpoint: float
    entry: float
    stop_loss: float

    @classmethod
    def from_candidate(
        cls,
        *,
        signal_timestamp: datetime,
        candidate: LongSetupCandidate,
        score: LongScore,
    ) -> "LongSignalDiagnostic":
        sweep = candidate.liquidity_sweep
        order_block = candidate.order_block
        return cls(
            signal_timestamp=signal_timestamp,
            setup_type=candidate.type.value,
            score_total=score.total,
            score_grade=score.grade.value,
            score_structure=score.structure,
            score_liquidity=score.liquidity,
            score_order_block=score.order_block,
            score_fvg=score.fvg,
            score_momentum=score.momentum,
            score_volume=score.volume,
            score_location=score.location,
            sweep_timestamp=sweep.timestamp,
            sweep_price=sweep.swept_price,
            sweep_extreme=sweep.extreme_price,
            sweep_reclaim_close=sweep.reclaim_close,
            order_block_timestamp=order_block.timestamp,
            order_block_status=order_block.status.value,
            order_block_low=order_block.low,
            order_block_high=order_block.high,
            order_block_midpoint=order_block.midpoint,
            entry=candidate.entry,
            stop_loss=candidate.stop_loss,
        )
