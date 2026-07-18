from datetime import datetime

from core.decision import Decision
from core.setup import Setup
from core.trade_request import TradeRequest
from core.trend import Trend
from infrastructure.bybit.bybit_order_mapper import BybitOrderMapper


def main():

    setup = Setup(
        index=100,
        timestamp=datetime.now(),
        trend=Trend.BULLISH,
        entry=100000,
        stop_loss=99000,
        take_profit=102000,
    )

    request = TradeRequest(
        symbol="BTCUSDT",
        decision=Decision.BUY,
        entry=setup.entry,
        stop_loss=setup.stop_loss,
        take_profit=setup.take_profit,
        volume=0.001,
        setup=setup,
    )

    order = BybitOrderMapper.to_order_request(request)

    print(order)


if __name__ == "__main__":
    main()