from core.position import Position
from core.trade import Trade
from core.trade_statistics import TradeStatistics


class NullNotifier:
    def position_opened(self, position: Position) -> None:
        pass

    def trade_closed(
        self,
        trade: Trade,
        statistics: TradeStatistics,
    ) -> None:
        pass
