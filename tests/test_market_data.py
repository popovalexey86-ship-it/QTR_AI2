from datetime import UTC, datetime

from core.candle import Candle
from core.market_data import MarketData
from infrastructure.bybit.bybit_mapper import BybitMapper




def test_to_market_data():

    response = {
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
                ],
                [
                    "1721217660000",
                    "118100",
                    "118300",
                    "118000",
                    "118250",
                    "98.15",
                    "11600000",
                ],
            ]
        }
    }

    market_data = BybitMapper.to_market_data(
        response=response,
        symbol="BTCUSDT",
        timeframe="1",
    )

    assert isinstance(
        market_data,
        MarketData,
    )

    assert market_data.timeframe == "1"

    assert len(market_data.candles) == 2

    assert market_data.candles[0] == Candle(
        timestamp=datetime.fromtimestamp(
            1721217600,
            UTC,
        ),
        open=118000.0,
        high=118200.0,
        low=117900.0,
        close=118100.0,
        volume=125.37,
    )

    assert market_data.candles[1] == Candle(
        timestamp=datetime.fromtimestamp(
            1721217660,
            UTC,
        ),
        open=118100.0,
        high=118300.0,
        low=118000.0,
        close=118250.0,
        volume=98.15,
    )