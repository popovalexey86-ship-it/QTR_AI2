from pybit.unified_trading import HTTP

from infrastructure.config import Config


class BybitClient:

    def __init__(
        self,
        config: Config,
    ):
        self._session = HTTP(
            testnet=config.bybit_testnet,
            api_key=config.bybit_api_key,
            api_secret=config.bybit_api_secret,
        )

    def get_server_time(self) -> dict:
        return self._session.get_server_time()

    def get_klines(
        self,
        category: str,
        symbol: str,
        interval: str,
        limit: int,
    ) -> dict:
        return self._session.get_kline(
            category=category,
            symbol=symbol,
            interval=interval,
            limit=limit,
        )

    def place_order(
        self,
        **kwargs,
    ) -> dict:
        return self._session.place_order(**kwargs)

    def get_positions(
        self,
        category: str,
        symbol: str,
    ) -> dict:
        return self._session.get_positions(
            category=category,
            symbol=symbol,
        )

    def get_closed_pnl(
        self,
        category: str,
        symbol: str,
        limit: int = 1,
    ) -> dict:
        return self._session.get_closed_pnl(
            category=category,
            symbol=symbol,
            limit=limit,
        )