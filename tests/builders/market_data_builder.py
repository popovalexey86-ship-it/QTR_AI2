from core.candle import Candle
from core.market_data import MarketData


class MarketDataBuilder:
    def __init__(self):
        self._symbol = "BTCUSDT"
        self._timeframe = "15m"
        self._candles: list[Candle] = []

    def symbol(self, value: str) -> "MarketDataBuilder":
        self._symbol = value
        return self

    def timeframe(self, value: str) -> "MarketDataBuilder":
        self._timeframe = value
        return self

    def add_candle(self, candle: Candle) -> "MarketDataBuilder":
        self._candles.append(candle)
        return self

    def build(self) -> MarketData:
        return MarketData(
            symbol=self._symbol,
            timeframe=self._timeframe,
            candles=self._candles,
        )