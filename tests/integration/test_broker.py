from core.decision import Decision
from core.setup import Setup
from core.trade_request import TradeRequest
from core.trend import Trend
from infrastructure.container import Container


def main() -> None:
    container = Container()

    print("=" * 60)
    print("COLLECT MARKET DATA")
    print("=" * 60)

    market_data = container.collector.collect()
    last = market_data.last

    print(last)

    entry = last.close
    stop_loss = entry * 0.99
    take_profit = entry * 1.02

    setup = Setup(
        index=market_data.count - 1,
        timestamp=last.timestamp,
        trend=Trend.BULLISH,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )

    request = TradeRequest(
        symbol="BTCUSDT",
        setup=setup,
        decision=Decision.BUY,
        volume=0.001,
    )

    print()
    print("=" * 60)
    print("OPEN POSITION")
    print("=" * 60)

    position = container.broker.open_position(request)

    print(position)

    print()
    print("=" * 60)
    print("OPEN POSITIONS")
    print("=" * 60)

    positions = container.broker.get_positions()

    if positions:
        for position in positions:
            print(position)
    else:
        print("No open positions.")

    print()
    print("=" * 60)
    print("CLOSE POSITION")
    print("=" * 60)

    container.broker.close_position(position)

    print("Position closed.")

    print()
    print("=" * 60)
    print("OPEN POSITIONS")
    print("=" * 60)

    positions = container.broker.get_positions()

    if positions:
        for position in positions:
            print(position)
    else:
        print("No open positions.")


if __name__ == "__main__":
    main()