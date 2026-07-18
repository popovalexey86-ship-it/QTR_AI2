from core.bos_type import BOSType


def test_bos_type_values():
    assert BOSType.BULLISH.value == "BULLISH"
    assert BOSType.BEARISH.value == "BEARISH"