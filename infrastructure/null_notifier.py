from core.position import Position
from core.trade import Trade
from core.trade_statistics import TradeStatistics
from core.pending_entry_event import PendingEntryEvent


class NullNotifier:
    def runtime_started(self) -> None:
        pass

    def runtime_stopped(self) -> None:
        pass

    def runtime_failed(self, error_message: str) -> None:
        pass

    def position_opened(self, position: Position) -> None:
        pass

    def pending_entry_event(self, event: PendingEntryEvent) -> None:
        pass

    def trade_closed(
        self,
        trade: Trade,
        statistics: TradeStatistics,
    ) -> None:
        pass
