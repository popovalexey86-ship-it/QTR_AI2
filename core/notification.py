from typing import Protocol

from core.position import Position
from core.trade import Trade
from core.trade_statistics import TradeStatistics


class NotificationError(RuntimeError):
    """Raised when a notification cannot be delivered."""


class NotificationPort(Protocol):
    def runtime_started(self) -> None: ...

    def runtime_stopped(self) -> None: ...

    def runtime_failed(self, error_message: str) -> None: ...

    def position_opened(self, position: Position) -> None: ...

    def trade_closed(
        self,
        trade: Trade,
        statistics: TradeStatistics,
    ) -> None: ...
