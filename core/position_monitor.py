from core.execution import Execution
from core.logger import logger
from core.notification import NotificationError, NotificationPort
from core.position import Position
from core.trade import Trade
from core.trade_journal import TradeJournalPort, TradeJournalWriteError
from core.trade_statistics import TradeStatistics


class PositionMonitor:
    def __init__(
        self,
        execution: Execution,
        statistics: TradeStatistics,
        journal: TradeJournalPort,
        notifier: NotificationPort,
    ) -> None:
        self._execution = execution
        self._statistics = statistics
        self._journal = journal
        self._notifier = notifier

        self._position: Position | None = None
        self._previous_position: Position | None = None
        self._last_open_position_ticket: str | None = None
        self._last_closed_trade_ticket: str | None = None
        self._closed_trade_baseline_initialized = False

    def update(self) -> None:
        position = self._execution.get_open_position()
        observed_position_close = position is None and self._position is not None

        if position is None:
            if observed_position_close:
                self._previous_position = self._position
                self._position = None
                self._last_open_position_ticket = None
        else:
            if position.ticket != self._last_open_position_ticket:
                self._last_open_position_ticket = position.ticket

                logger.info(
                    "Position opened | ticket=%s symbol=%s decision=%s entry=%s",
                    position.ticket,
                    position.symbol,
                    position.decision.name,
                    position.entry,
                )

                try:
                    self._notifier.position_opened(position)
                except NotificationError as error:
                    logger.error(
                        "Position-opened notification failed. Ticket=%s Error=%s",
                        position.ticket,
                        error,
                    )

            self._previous_position = self._position
            self._position = position

        self._inspect_closed_trade(
            observed_position_close=observed_position_close,
        )

    def _inspect_closed_trade(self, *, observed_position_close: bool) -> None:
        trade = self._execution.get_last_closed_trade()

        if not self._closed_trade_baseline_initialized:
            self._closed_trade_baseline_initialized = True
            self._last_closed_trade_ticket = (
                None if trade is None else trade.ticket
            )
            return

        if trade is None:
            if observed_position_close:
                logger.warning("Position closed, but no closed trade was found.")
            return

        if trade.ticket == self._last_closed_trade_ticket:
            return

        self._record_closed_trade(trade)

    def _record_closed_trade(self, trade: Trade) -> None:
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

        try:
            self._notifier.trade_closed(trade, self._statistics)
        except NotificationError as error:
            logger.error(
                "Trade-closed notification failed. Ticket=%s Error=%s",
                trade.ticket,
                error,
            )

    @property
    def position(self) -> Position | None:
        return self._position

    @property
    def previous_position(self) -> Position | None:
        return self._previous_position

    def has_open_position(self) -> bool:
        return self._position is not None
