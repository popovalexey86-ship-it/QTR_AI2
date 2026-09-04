from dataclasses import dataclass
from enum import Enum

from core.liquidity_sweep import LiquiditySweep
from core.order_block import OrderBlock


class LongSetupType(Enum):
    SWEEP_RECLAIM_ORDER_BLOCK = "sweep_reclaim_order_block"


@dataclass(frozen=True, slots=True)
class LongSetupCandidate:
    """Long-only SMC candidate before scoring and risk approval."""

    type: LongSetupType
    liquidity_sweep: LiquiditySweep
    order_block: OrderBlock
    entry: float
    stop_loss: float

    def __post_init__(self) -> None:
        if self.stop_loss >= self.entry:
            raise ValueError("long setup stop loss must be below entry")
