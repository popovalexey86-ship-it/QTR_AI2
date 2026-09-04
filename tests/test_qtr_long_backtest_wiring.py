import pytest

from backtesting.qtr_long_backtest import create_qtr_long_backtest_runner
from strategies.qtr_long.decision_engine import LongDecisionEngine
from strategies.qtr_long.risk_manager import LongOnlyRiskManager
from strategies.qtr_long.strategy import QTRLongStrategy


def test_qtr_long_backtest_uses_long_only_stack():
    runner = create_qtr_long_backtest_runner(symbol="BTCUSDT")

    engine = runner._engine
    assert isinstance(engine._strategy, QTRLongStrategy)
    assert isinstance(engine._decision_engine, LongDecisionEngine)
    assert isinstance(engine._risk_manager, LongOnlyRiskManager)


def test_qtr_long_backtest_normalizes_symbol_through_risk_boundary():
    runner = create_qtr_long_backtest_runner(symbol="btcusdt")

    risk_manager = runner._engine._risk_manager
    assert isinstance(risk_manager, LongOnlyRiskManager)
    assert risk_manager._symbol == "BTCUSDT"


def test_qtr_long_backtest_rejects_invalid_genesis_parameters():
    with pytest.raises(ValueError):
        create_qtr_long_backtest_runner(symbol="BTCUSDT", minimum_score=101)

    with pytest.raises(ValueError):
        create_qtr_long_backtest_runner(symbol="BTCUSDT", risk_reward=0)

    with pytest.raises(ValueError):
        create_qtr_long_backtest_runner(symbol="BTCUSDT", volume=0)
