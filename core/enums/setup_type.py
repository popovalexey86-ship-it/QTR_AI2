from enum import Enum


class SetupType(Enum):
    ORDER_BLOCK = "order_block"
    BREAKER = "breaker"
    FVG = "fair_value_gap"
    LIQUIDITY_SWEEP = "liquidity_sweep"