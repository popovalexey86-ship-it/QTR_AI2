from datetime import datetime

import pytest

from core.choch import CHOCH
from core.choch_type import CHOCHType


def test_create_choch():
    choch = CHOCH(
        index=15,
        timestamp=datetime(2025, 1, 1),
        price=50000,
        type=CHOCHType.BULLISH,
    )

    assert choch.index == 15
    assert choch.price == 50000
    assert choch.type == CHOCHType.BULLISH


def test_choch_is_immutable():
    choch = CHOCH(
        index=15,
        timestamp=datetime(2025, 1, 1),
        price=50000,
        type=CHOCHType.BULLISH,
    )

    with pytest.raises(AttributeError):
        choch.price = 60000
