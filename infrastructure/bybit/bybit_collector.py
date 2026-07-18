from core.market_data import MarketData

from infrastructure.bybit.bybit_client import BybitClient
from infrastructure.bybit.bybit_mapper import BybitMapper


class BybitCollector:

    def __init__(
        self,
        client: BybitClient,
        category: str,
        symbol: str,
        interval: str,
    ):
        self._client = client
        self._category = category
        self._symbol = symbol
        self._interval = interval

    def collect(
        self,
        limit: int = 500,
    ) -> MarketData:

        response = self._client.get_klines(
            category=self._category,
            symbol=self._symbol,
            interval=self._interval,
            limit=limit,
        )

        return BybitMapper.to_market_data(
            response=response,
            symbol=self._symbol,
            timeframe=self._interval,
        )