from datetime import datetime

from core.decision import Decision
from core.risk_manager import RiskManager
from core.setup import Setup
from core.trade_request import TradeRequest
from core.trend import Trend


def make_setup(
    trend: Trend,
    entry: float,
    stop_loss: float,
) -> Setup:
    return Setup(
        index=10,
        timestamp=datetime(2025, 1, 1),
        trend=trend,
        entry=entry,
        stop_loss=stop_loss,
    )


def test_build_trade_request():

    engine = RiskManager(risk_reward=2.0, symbol="BTCUSDT", volume=0.01)

    setup = make_setup(
        trend=Trend.BULLISH,
        entry=100.0,
        stop_loss=95.0,
    )

    request = engine.build(
        setup=setup,
        decision=Decision.BUY,
    )

    assert isinstance(request, TradeRequest)

    assert request.decision == Decision.BUY
    assert request.entry == 100.0
    assert request.stop_loss == 95.0
    assert request.setup is setup


def test_calculate_take_profit_buy():

    engine = RiskManager(risk_reward=2.0, symbol="BTCUSDT", volume=0.01)

    request = engine.build(
        setup=make_setup(
            trend=Trend.BULLISH,
            entry=100.0,
            stop_loss=95.0,
        ),
        decision=Decision.BUY,
    )

    assert request.take_profit == 110.0


def test_calculate_take_profit_sell():

    engine = RiskManager(risk_reward=2.0, symbol="BTCUSDT", volume=0.01)

    request = engine.build(
        setup=make_setup(
            trend=Trend.BEARISH,
            entry=100.0,
            stop_loss=105.0,
        ),
        decision=Decision.SELL,
    )

    assert request.take_profit == 90.0


def test_configured_symbol_and_volume_are_used() -> None:
    manager = RiskManager(
        risk_reward=2.0,
        symbol="ethusdt",
        volume=0.25,
    )

    request = manager.build(
        setup=make_setup(Trend.BULLISH, 100.0, 95.0),
        decision=Decision.BUY,
    )

    assert request.symbol == "ETHUSDT"
    assert request.volume == 0.25
