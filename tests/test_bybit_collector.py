from unittest.mock import Mock

from core.market_data import MarketData
from infrastructure.bybit.bybit_collector import BybitCollector


def test_collect_returns_market_data():

    client = Mock()

    client.get_klines.return_value = {
        "result": {
            "list": [
                [
                    "1721217600000",
                    "118000",
                    "118200",
                    "117900",
                    "118100",
                    "125.37",
                    "14700000",
                ]
            ]
        }
    }

    collector = BybitCollector(client)

    market_data = collector.collect(
        category="linear",
        symbol="BTCUSDT",
        interval="1",
        limit=1,
    )
    assert market_data.symbol == "BTCUSDT"
    assert market_data.timeframe == "1"

    assert isinstance(
        market_data,
        MarketData,
    )

    assert len(market_data.candles) == 1

    assert market_data.candles[0].close == 118100.0