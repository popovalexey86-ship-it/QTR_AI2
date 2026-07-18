from datetime import UTC, datetime

from core.candle import Candle
from core.market_data import MarketData


class BybitMapper:

    @staticmethod
    def to_candle(raw: list[str]) -> Candle:

        return Candle(
            timestamp=datetime.fromtimestamp(
                int(raw[0]) / 1000,
                UTC,
            ),
            open=float(raw[1]),
            high=float(raw[2]),
            low=float(raw[3]),
            close=float(raw[4]),
            volume=float(raw[5]),
        )

    @staticmethod
    def to_market_data(
        response: dict,
        symbol: str,
        timeframe: str,
    ) -> MarketData:

        candles = [BybitMapper.to_candle(raw) for raw in response["result"]["list"]]

        return MarketData(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
        )
