from collections.abc import Sequence

from backtesting.backtest_result import BacktestResult
from backtesting.simulated_broker import SimulatedBroker
from core.decision_engine import DecisionEngine
from core.execution import Execution
from core.market_data import MarketData
from core.position_monitor import PositionMonitor
from core.risk_manager import RiskManager
from core.trade_journal import TradeJournal
from core.trade_statistics import TradeStatistics
from engine.trading_engine import TradingEngine
from infrastructure.null_notifier import NullNotifier
from strategies.strategy import Strategy


class BacktestInputError(ValueError):
    """Raised when historical input violates the backtest contract."""


class BacktestRunner:
    """Single-use deterministic runner for ordered, single-symbol snapshots."""

    def __init__(
        self,
        symbol: str,
        strategy: Strategy,
        decision_engine: DecisionEngine,
        risk_manager: RiskManager,
    ) -> None:
        if not symbol:
            raise BacktestInputError("Backtest symbol cannot be empty.")

        self._symbol = symbol
        self._broker = SimulatedBroker(symbol=symbol)
        self._execution = Execution(self._broker)
        self._journal = TradeJournal()
        self._statistics = TradeStatistics()
        self._position_monitor = PositionMonitor(
            execution=self._execution,
            statistics=self._statistics,
            journal=self._journal,
            notifier=NullNotifier(),
        )
        self._engine = TradingEngine(
            strategy=strategy,
            decision_engine=decision_engine,
            risk_manager=risk_manager,
            execution=self._execution,
            position_monitor=self._position_monitor,
        )
        self._has_run = False

    def run(self, snapshots: Sequence[MarketData]) -> BacktestResult:
        if self._has_run:
            raise RuntimeError("A BacktestRunner instance can only run once.")

        ordered_snapshots = self._validate_snapshots(snapshots)
        self._has_run = True

        for market_data in ordered_snapshots:
            self._broker.update_market(market_data.last)
            self._engine.process(market_data)
            # TradingEngine checks positions before execution. Synchronize the
            # monitor after execution so a close on the next candle is observed.
            self._position_monitor.update()

        trades = self._journal.trades
        gross_profit = sum(trade.pnl for trade in trades if trade.pnl > 0)
        gross_loss = -sum(trade.pnl for trade in trades if trade.pnl < 0)

        return BacktestResult(
            symbol=self._symbol,
            candles_processed=len(ordered_snapshots),
            total_trades=self._statistics.total_trades,
            winning_trades=self._statistics.wins,
            losing_trades=self._statistics.losses,
            win_rate=self._statistics.win_rate,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            net_pnl=self._statistics.net_pnl,
            has_open_position=self._broker.get_open_position() is not None,
            completed_trades=trades,
        )

    def _validate_snapshots(
        self,
        snapshots: Sequence[MarketData],
    ) -> tuple[MarketData, ...]:
        if not snapshots:
            raise BacktestInputError("Historical market data cannot be empty.")

        validated = tuple(snapshots)
        previous_timestamp = None
        terminal_timestamps = set()

        for position, market_data in enumerate(validated, start=1):
            if market_data.symbol != self._symbol:
                raise BacktestInputError(
                    "Historical market data must contain exactly one symbol: "
                    f"expected {self._symbol!r}, got {market_data.symbol!r}."
                )
            if not market_data.candles:
                raise BacktestInputError(
                    f"MarketData snapshot {position} contains no candles."
                )

            candle_timestamps = [
                candle.timestamp for candle in market_data.candles
            ]
            if len(candle_timestamps) != len(set(candle_timestamps)):
                raise BacktestInputError(
                    f"MarketData snapshot {position} has duplicate timestamps."
                )
            if any(
                current <= previous
                for previous, current in zip(
                    candle_timestamps,
                    candle_timestamps[1:],
                )
            ):
                raise BacktestInputError(
                    f"MarketData snapshot {position} is not chronological."
                )

            timestamp = market_data.last.timestamp
            if timestamp in terminal_timestamps:
                raise BacktestInputError(
                    f"Duplicate snapshot timestamp: {timestamp.isoformat()}."
                )
            if previous_timestamp is not None and timestamp < previous_timestamp:
                raise BacktestInputError(
                    "Historical snapshots must be sorted chronologically."
                )

            terminal_timestamps.add(timestamp)
            previous_timestamp = timestamp

        return validated
