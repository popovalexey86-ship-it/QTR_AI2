from datetime import datetime

from core.broker import Broker
from core.decision import Decision
from core.execution import Execution
from core.position import Position
from core.setup import Setup
from core.trade_request import TradeRequest
from core.trend import Trend


def make_setup() -> Setup:
    return Setup(
        index=10,
        timestamp=datetime(2025, 1, 1),
        trend=Trend.BULLISH,
        entry=100.0,
        stop_loss=95.0,
    )


def make_request() -> TradeRequest:
    return TradeRequest(
        decision=Decision.BUY,
        entry=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        volume=0.10,
        setup=make_setup(),
    )


class FakeBroker(Broker):

    def open_position(
        self,
        request: TradeRequest,
    ) -> Position:

        return Position(
            ticket=1,
            decision=request.decision,
            entry=request.entry,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            volume=request.volume,
            opened_at=datetime(2025, 1, 1),
        )

    def close_position(
        self,
        ticket: int,
    ) -> None:
        pass

    def get_positions(
        self,
    ) -> list[Position]:
        return []


def test_execute_trade_request():

    broker = FakeBroker()

    engine = Execution(
        broker=broker,
    )

    position = engine.execute(
        request=make_request(),
    )

    assert isinstance(position, Position)

    assert position.ticket == 1
    assert position.decision == Decision.BUY
    assert position.entry == 100.0
    assert position.stop_loss == 95.0
    assert position.take_profit == 110.0
    assert position.volume == 0.10