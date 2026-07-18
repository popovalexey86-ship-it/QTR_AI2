from core.market_data import MarketData

from infrastructure.bybit.bybit_client import BybitClient
from infrastructure.bybit.bybit_mapper import BybitMapper


class BybitCollector:

    def __init__(
        self,
        client: BybitClient,
        category: str = "linear",
        symbol: str = "BTCUSDT",
        interval: str = "1",
    ):
        self._client = client
        self._category = category
        self._symbol = symbol
        self._interval = interval

    def collect(
        self,
        category: str | None = None,
        symbol: str | None = None,
        interval: str | None = None,
        limit: int = 500,
    ) -> MarketData:

        category = category or self._category
        symbol = symbol or self._symbol
        interval = interval or self._interval

        response = self._client.get_klines(
            category=category,
            symbol=symbol,
            interval=interval,
            limit=limit,
        )

        return BybitMapper.to_market_data(
            response=response,
            symbol=symbol,
            timeframe=interval,
        )
