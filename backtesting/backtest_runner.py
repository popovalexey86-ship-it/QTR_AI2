from collections.abc import Iterable
from datetime import datetime

from backtesting.backtest_result import BacktestResult
from backtesting.simulated_broker import SimulatedBroker, SimulatedOrderRejected
from core.decision_engine import DecisionEngine
from core.execution import Execution
from core.logger import logger
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
        pending_entry_ttl_candles: int = 4,
    ) -> None:
        if not symbol:
            raise BacktestInputError("Backtest symbol cannot be empty.")

        self._symbol = symbol
        self._broker = SimulatedBroker(
            symbol=symbol,
            pending_entry_ttl_candles=pending_entry_ttl_candles,
        )
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

    def run(self, snapshots: Iterable[MarketData]) -> BacktestResult:
        if self._has_run:
            raise RuntimeError("A BacktestRunner instance can only run once.")

        self._has_run = True
        candles_processed = 0
        rejected_orders = 0
        previous_timestamp = None

        for position, market_data in enumerate(snapshots, start=1):
            previous_timestamp = self._validate_snapshot(
                market_data,
                position=position,
                previous_timestamp=previous_timestamp,
            )
            self._broker.update_market(market_data.last)
            try:
                self._engine.process(market_data)
            except SimulatedOrderRejected:
                rejected_orders += 1
                logger.info(
                    "Simulated pending entry rejected because protective "
                    "levels are invalid for its limit price."
                )
            # Synchronize a newly submitted entry or confirmed position state.
            # Ticket deduplication prevents a same-candle trade from being
            # counted again after TradingEngine's initial monitor update.
            self._position_monitor.update()
            candles_processed += 1

        if candles_processed == 0:
            raise BacktestInputError("Historical market data cannot be empty.")

        trades = self._journal.trades
        gross_profit = sum(trade.pnl for trade in trades if trade.pnl > 0)
        gross_loss = -sum(trade.pnl for trade in trades if trade.pnl < 0)

        final_pending_entry = self._broker.get_pending_entry()
        return BacktestResult(
            symbol=self._symbol,
            candles_processed=candles_processed,
            total_trades=self._statistics.total_trades,
            winning_trades=self._statistics.wins,
            losing_trades=self._statistics.losses,
            win_rate=self._statistics.win_rate,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            net_pnl=self._statistics.net_pnl,
            has_open_position=self._broker.get_open_position() is not None,
            completed_trades=trades,
            rejected_orders=rejected_orders,
            has_pending_entry=final_pending_entry is not None,
            final_pending_entry=final_pending_entry,
            submitted_entries=self._broker.submitted_entry_count,
            filled_entries=self._broker.filled_entry_count,
            expired_entries=self._broker.expired_entry_count,
        )

    def _validate_snapshot(
        self,
        market_data: MarketData,
        *,
        position: int,
        previous_timestamp: datetime | None,
    ) -> datetime:
        if market_data.symbol != self._symbol:
            raise BacktestInputError(
                "Historical market data must contain exactly one symbol: "
                f"expected {self._symbol!r}, got {market_data.symbol!r}."
            )
        if not market_data.candles:
            raise BacktestInputError(
                f"MarketData snapshot {position} contains no candles."
            )

        candle_timestamps = [candle.timestamp for candle in market_data.candles]
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
        if previous_timestamp is not None:
            if timestamp == previous_timestamp:
                raise BacktestInputError(
                    f"Duplicate snapshot timestamp: {timestamp.isoformat()}."
                )
            if timestamp < previous_timestamp:
                raise BacktestInputError(
                    "Historical snapshots must be sorted chronologically."
                )
        return timestamp
