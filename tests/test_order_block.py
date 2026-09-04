from datetime import datetime

import pytest

from core.order_block import (
    OrderBlock,
    OrderBlockDirection,
    OrderBlockStatus,
)


def make_order_block() -> OrderBlock:
    return OrderBlock(
        index=5,
        timestamp=datetime(2025, 1, 1),
        direction=OrderBlockDirection.BULLISH,
        low=95.0,
        high=100.0,
    )


def test_order_block_midpoint_and_contains():
    order_block = make_order_block()

    assert order_block.midpoint == 97.5
    assert order_block.contains(95.0)
    assert order_block.contains(97.5)
    assert order_block.contains(100.0)
    assert not order_block.contains(94.99)
    assert not order_block.contains(100.01)


def test_order_block_is_fresh_by_default():
    assert make_order_block().status == OrderBlockStatus.FRESH


def test_order_block_rejects_inverted_range():
    with pytest.raises(ValueError, match="low must be <= high"):
        OrderBlock(
            index=5,
            timestamp=datetime(2025, 1, 1),
            direction=OrderBlockDirection.BULLISH,
            low=101.0,
            high=100.0,
        )


def test_order_block_is_immutable():
    order_block = make_order_block()

    with pytest.raises(AttributeError):
        order_block.low = 90.0


def test_with_status_returns_new_order_block():
    order_block = make_order_block()

    mitigated = order_block.with_status(OrderBlockStatus.MITIGATED)

    assert order_block.status == OrderBlockStatus.FRESH
    assert mitigated.status == OrderBlockStatus.MITIGATED
    assert mitigated is not order_block
