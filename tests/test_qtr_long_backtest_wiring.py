from datetime import UTC, datetime, timedelta

import pytest

from backtesting.qtr_long_backtest import (
    create_qtr_long_backtest_runner,
    run_qtr_long_backtest,
)
from core.candle import Candle
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


def test_qtr_long_historical_path_processes_chronological_candles():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        Candle(
            timestamp=start + timedelta(minutes=15 * index),
            open=100 + index,
            high=101 + index,
            low=99 + index,
            close=100.5 + index,
            volume=10,
            index=index,
        )
        for index in range(20)
    ]

    result = run_qtr_long_backtest(
        candles,
        symbol="BTCUSDT",
        interval="15",
    )

    assert result.symbol == "BTCUSDT"
    assert result.candles_processed == 20
    assert all(trade.decision.name == "BUY" for trade in result.completed_trades)
