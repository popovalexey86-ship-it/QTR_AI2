import time

from core.broker import Broker
from core.exceptions import BrokerError, OrderRejectedError
from core.position import Position
from core.trade import Trade
from core.trade_request import TradeRequest
from infrastructure.bybit.bybit_trade_mapper import BybitTradeMapper
from infrastructure.bybit.bybit_client import BybitClient
from infrastructure.bybit.bybit_order_mapper import BybitOrderMapper
from infrastructure.bybit.bybit_position_mapper import BybitPositionMapper


class BybitBroker(Broker):

    def __init__(
        self,
        client: BybitClient,
        category: str,
        symbol: str,
        order_mapper: BybitOrderMapper | None = None,
        position_mapper: BybitPositionMapper | None = None,
    ):
        self._client = client
        self._order_mapper = order_mapper or BybitOrderMapper()
        self._position_mapper = position_mapper or BybitPositionMapper()
        self._category = category
        self._symbol = symbol

    def open_position(
        self,
        request: TradeRequest,
    ) -> Position:

        order = self._order_mapper.to_order_request(request)

        response = self._client.place_order(
            category=self._category,
            **order,
        )

        if response.get("retCode", 0) != 0:
            raise OrderRejectedError(
                f'Bybit error {response["retCode"]}: {response["retMsg"]}'
            )

        if "result" not in response:
            raise BrokerError("Invalid Bybit response.")

        try:
            return self._position_mapper.from_order_response(
                response=response,
                request=request,
            )
        except AttributeError:
            pass

        for _ in range(5):
            positions = self.get_positions()
            if positions:
                return positions[0]
            time.sleep(0.2)

        raise BrokerError("Position was not found after order execution.")

    def close_position(
        self,
        position: Position,
    ) -> None:

        order = self._order_mapper.to_close_order_request(position)

        response = self._client.place_order(
            category=self._category,
            **order,
        )

        if response.get("retCode", 0) != 0:
            raise OrderRejectedError(
                f'Bybit error {response["retCode"]}: {response["retMsg"]}'
            )

    def get_positions(
        self,
    ) -> list[Position]:

        response = self._client.get_positions(
            category=self._category,
            symbol=self._symbol,
        )

        if response.get("retCode", 0) != 0:
            raise BrokerError(
                f'Bybit error {response["retCode"]}: {response["retMsg"]}'
            )

        positions: list[Position] = []

        for item in response.get("result", {}).get("list", []):

            if float(item.get("size", 0)) == 0:
                continue

            positions.append(
                self._position_mapper.from_position(item)
            )

        return positions

    def get_open_position(
        self,
    ) -> Position | None:

        positions = self.get_positions()

        if not positions:
            return None

        return positions[0]

    def get_last_closed_trade(
        self,
    ) -> Trade | None:

       response = self._client.get_closed_pnl(
           category=self._category,
           symbol=self._symbol,
           limit=1,
       )

       if response.get("retCode", 0) != 0:
           raise BrokerError(
               f'Bybit error {response["retCode"]}: {response["retMsg"]}'
           )

       trades = response.get("result", {}).get("list", [])

       if not trades:
           return None

       return BybitTradeMapper.from_closed_pnl(trades[0])