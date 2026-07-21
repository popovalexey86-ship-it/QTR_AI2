from core.position import Position
from core.trade import Trade
from core.trade_statistics import TradeStatistics


class NullNotifier:
    def runtime_started(self) -> None:
        pass

    def runtime_stopped(self) -> None:
        pass

    def runtime_failed(self, error_message: str) -> None:
        pass

    def position_opened(self, position: Position) -> None:
        pass

    def trade_closed(
        self,
        trade: Trade,
        statistics: TradeStatistics,
    ) -> None:
        pass
