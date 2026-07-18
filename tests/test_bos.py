from datetime import datetime

import pytest

from core.bos import BOS
from core.bos_type import BOSType


def test_create_bos():
    bos = BOS(
        index=10,
        timestamp=datetime(2025, 1, 1),
        price=50000,
        type=BOSType.BULLISH,
    )

    assert bos.index == 10
    assert bos.price == 50000
    assert bos.type == BOSType.BULLISH


def test_bos_is_immutable():
    bos = BOS(
        index=10,
        timestamp=datetime(2025, 1, 1),
        price=50000,
        type=BOSType.BULLISH,
    )

    with pytest.raises(AttributeError):
        bos.price = 60000
