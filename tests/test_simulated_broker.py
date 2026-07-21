from datetime import UTC, datetime, timedelta

import pytest

from backtesting.simulated_broker import (
    SimulatedBroker,
    SimulatedOrderRejected,
)
from core.candle import Candle
from core.decision import Decision
from core.setup import Setup
from core.trade_request import TradeRequest
from core.trend import Trend


START = datetime(2025, 1, 1, tzinfo=UTC)


def candle(
    minute: int,
    *,
    close: float,
    high: float | None = None,
    low: float | None = None,
) -> Candle:
    return Candle(
        timestamp=START + timedelta(minutes=minute),
        open=close,
        high=close if high is None else high,
        low=close if low is None else low,
        close=close,
        volume=1.0,
    )


def request(
    decision: Decision,
    *,
    entry: float = 100.0,
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> TradeRequest:
    bullish = decision == Decision.BUY
    stop_loss = stop_loss if stop_loss is not None else (95.0 if bullish else 105.0)
    take_profit = (
        take_profit if take_profit is not None else (110.0 if bullish else 90.0)
    )
    setup = Setup(
        index=0,
        timestamp=START,
        trend=Trend.BULLISH if bullish else Trend.BEARISH,
        entry=entry,
        stop_loss=stop_loss,
    )
    return TradeRequest(
        symbol="BTCUSDT",
        decision=decision,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        volume=0.01,
        setup=setup,
    )


@pytest.mark.parametrize(
    "decision, close",
    [(Decision.BUY, 102.0), (Decision.SELL, 98.0)],
)
def test_market_fill_uses_signal_candle_close(decision, close):
    broker = SimulatedBroker("BTCUSDT")
    broker.update_market(candle(0, close=close))

    position = broker.open_position(request(decision, entry=100.0))

    assert position.entry == close
    assert position.stop_loss == (95.0 if decision == Decision.BUY else 105.0)
    assert position.take_profit == (110.0 if decision == Decision.BUY else 90.0)


def test_pnl_uses_actual_market_fill_and_exit_starts_next_candle():
    broker = SimulatedBroker("BTCUSDT")
    broker.update_market(candle(0, close=102.0, high=120.0, low=90.0))
    position = broker.open_position(request(Decision.BUY))

    assert broker.get_open_position() is position
    assert broker.get_last_closed_trade() is None

    broker.update_market(candle(1, close=108.0, high=111.0, low=100.0))
    trade = broker.get_last_closed_trade()

    assert trade is not None
    assert trade.entry == 102.0
    assert trade.exit == 110.0
    assert trade.pnl == pytest.approx(0.08)


def test_stop_first_rule_is_preserved_when_both_levels_are_touched():
    broker = SimulatedBroker("BTCUSDT")
    broker.update_market(candle(0, close=100.0))
    broker.open_position(request(Decision.BUY))

    broker.update_market(candle(1, close=100.0, high=111.0, low=94.0))

    trade = broker.get_last_closed_trade()
    assert trade is not None
    assert trade.exit == 95.0
    assert trade.pnl == pytest.approx(-0.05)


@pytest.mark.parametrize(
    "trade_request, fill",
    [
        (request(Decision.BUY), 111.0),
        (request(Decision.BUY), 94.0),
        (request(Decision.SELL), 89.0),
        (request(Decision.SELL), 106.0),
    ],
)
def test_invalid_protective_level_side_rejects_order_without_using_ticket(
    trade_request,
    fill,
):
    broker = SimulatedBroker("BTCUSDT")
    broker.update_market(candle(0, close=fill))

    with pytest.raises(SimulatedOrderRejected, match="Protective levels"):
        broker.open_position(trade_request)

    assert broker.get_open_position() is None

    broker.update_market(candle(1, close=100.0))
    accepted = broker.open_position(request(Decision.BUY))
    assert accepted.ticket == "SIM-000001"
