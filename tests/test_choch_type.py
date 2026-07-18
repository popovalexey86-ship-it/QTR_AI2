from core.choch_type import CHOCHType


def test_choch_type_values():
    assert CHOCHType.BULLISH.value == "BULLISH"
    assert CHOCHType.BEARISH.value == "BEARISH"
