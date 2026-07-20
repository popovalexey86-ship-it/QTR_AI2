from core.execution import Execution
from core.logger import logger
from core.position import Position
from core.trade_journal import TradeJournalPort, TradeJournalWriteError
from core.trade_statistics import TradeStatistics


class PositionMonitor:
    def __init__(
        self,
        execution: Execution,
        statistics: TradeStatistics,
        journal: TradeJournalPort,
    ) -> None:
        self._execution = execution
        self._statistics = statistics
        self._journal = journal

        self._position: Position | None = None
        self._previous_position: Position | None = None
        self._last_open_position_ticket: str | None = None
        self._last_closed_trade_ticket: str | None = None

    def update(self) -> None:
        position = self._execution.get_open_position()

        if position is None:
            if self._position is not None:
                self._on_position_closed()
                self._previous_position = self._position
                self._position = None
                self._last_open_position_ticket = None
            return

        if position.ticket != self._last_open_position_ticket:
            logger.info(
                "Position opened | ticket=%s symbol=%s decision=%s entry=%s",
                position.ticket,
                position.symbol,
                position.decision.name,
                position.entry,
            )
            self._last_open_position_ticket = position.ticket

        self._previous_position = self._position
        self._position = position

    def _on_position_closed(self) -> None:
        trade = self._execution.get_last_closed_trade()

        if trade is None:
            logger.warning("Position closed, but no closed trade was found.")
            return

        if trade.ticket == self._last_closed_trade_ticket:
            return

        try:
            added = self._journal.add_trade(trade)
        except TradeJournalWriteError:
            logger.exception("Failed to persist closed trade. Ticket=%s", trade.ticket)
            raise

        self._last_closed_trade_ticket = trade.ticket

        if not added:
            return

        self._statistics.add_trade(trade)

        logger.info(
            "Position closed | ticket=%s symbol=%s decision=%s entry=%s "
            "exit=%s volume=%s pnl=%s fees=%s",
            trade.ticket,
            trade.symbol,
            trade.decision.name,
            trade.entry,
            trade.exit,
            trade.volume,
            trade.pnl,
            trade.fees,
        )

    @property
    def position(self) -> Position | None:
        return self._position

    @property
    def previous_position(self) -> Position | None:
        return self._previous_position

    def has_open_position(self) -> bool:
        return self._position is not None
