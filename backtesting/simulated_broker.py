from core.broker import Broker
from core.candle import Candle
from core.decision import Decision
from core.position import Position
from core.trade import Trade
from core.trade_request import TradeRequest


class SimulatedOrderRejected(ValueError):
    """Raised when fixed protective levels are invalid for a market fill."""


class SimulatedBroker(Broker):
    """Deterministic single-symbol broker with zero fees and no slippage.

    The completed signal candle close approximates a zero-slippage live market
    fill. Starting with the next processed candle, stop-loss and take-profit
    levels are evaluated. If both are touched by one candle, stop-loss wins to
    keep the result deterministic and conservative.
    """

    def __init__(self, symbol: str, fee: float = 0.0) -> None:
        if not symbol:
            raise ValueError("Backtest symbol cannot be empty.")
        if fee < 0:
            raise ValueError("Simulated fee cannot be negative.")

        self._symbol = symbol
        self._fee = fee
        self._position: Position | None = None
        self._last_closed_trade: Trade | None = None
        self._current_candle: Candle | None = None
        self._next_ticket = 1

    def update_market(self, candle: Candle) -> None:
        self._current_candle = candle
        position = self._position
        if position is None:
            return

        exit_price: float | None = None
        if position.decision == Decision.BUY:
            if candle.low <= position.stop_loss:
                exit_price = position.stop_loss
            elif candle.high >= position.take_profit:
                exit_price = position.take_profit
        elif position.decision == Decision.SELL:
            if candle.high >= position.stop_loss:
                exit_price = position.stop_loss
            elif candle.low <= position.take_profit:
                exit_price = position.take_profit

        if exit_price is not None:
            self._close_at(position, exit_price)

    def open_position(self, request: TradeRequest) -> Position:
        if self._position is not None:
            raise RuntimeError("A simulated position is already open.")
        if self._current_candle is None:
            raise RuntimeError("Market data must be processed before opening.")

        fill_price = self._current_candle.close
        self._validate_protective_levels(request, fill_price)

        ticket = f"SIM-{self._next_ticket:06d}"
        self._next_ticket += 1
        self._position = Position(
            ticket=ticket,
            # The runner's validated single symbol is authoritative. The
            # current RiskManager keeps a live BTCUSDT default in TradeRequest.
            symbol=self._symbol,
            decision=request.decision,
            entry=fill_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            volume=request.volume,
            opened_at=self._current_candle.timestamp,
        )
        return self._position

    @staticmethod
    def _validate_protective_levels(
        request: TradeRequest,
        fill_price: float,
    ) -> None:
        valid = False
        if request.decision == Decision.BUY:
            valid = request.stop_loss < fill_price < request.take_profit
        elif request.decision == Decision.SELL:
            valid = request.take_profit < fill_price < request.stop_loss

        if not valid:
            raise SimulatedOrderRejected(
                "Protective levels are invalid for the simulated market fill."
            )

    def close_position(self, position: Position) -> None:
        if self._position is None or self._position.ticket != position.ticket:
            raise ValueError("The requested simulated position is not open.")
        if self._current_candle is None:
            raise RuntimeError("No market price is available for closing.")

        self._close_at(position, self._current_candle.close)

    def get_positions(self) -> list[Position]:
        return [] if self._position is None else [self._position]

    def get_open_position(self) -> Position | None:
        return self._position

    def get_last_closed_trade(self) -> Trade | None:
        return self._last_closed_trade

    def _close_at(self, position: Position, exit_price: float) -> None:
        if self._current_candle is None:
            raise RuntimeError("No market price is available for closing.")

        price_change = exit_price - position.entry
        if position.decision == Decision.SELL:
            price_change = -price_change

        self._last_closed_trade = Trade(
            ticket=position.ticket,
            symbol=position.symbol,
            decision=position.decision,
            entry=position.entry,
            exit=exit_price,
            volume=position.volume,
            pnl=price_change * position.volume - self._fee,
            fees=self._fee,
            opened_at=position.opened_at,
            closed_at=self._current_candle.timestamp,
        )
        self._position = None
