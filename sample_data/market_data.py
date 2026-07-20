from datetime import UTC, datetime, timedelta

from core.candle import Candle
from core.market_data import MarketData


def create_market_data() -> MarketData:
    start = datetime.now(UTC)

    candles = []

    price = 100_000.0

    for i in range(10):
        candles.append(
            Candle(
                timestamp=start + timedelta(minutes=5 * i),
                open=price,
                high=price + 100,
                low=price - 100,
                close=price + 50,
                volume=1000.0,
            )
        )

        price += 50

    return MarketData(
        symbol="BTCUSDT",
        timeframe="5m",
        candles=candles,
    )