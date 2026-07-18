from core.decision import Decision


def test_decision_values():

    assert Decision.BUY.value == "BUY"
    assert Decision.SELL.value == "SELL"
    assert Decision.SKIP.value == "SKIP"
