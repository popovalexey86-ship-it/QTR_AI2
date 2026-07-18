
import time
from core.broker import Broker
from core.exceptions import (
    BrokerError,
    OrderRejectedError,
)
from core.position import Position
from core.trade_request import TradeRequest

from infrastructure.bybit.bybit_client import BybitClient
from infrastructure.bybit.bybit_order_mapper import BybitOrderMapper
from infrastructure.bybit.bybit_position_mapper import BybitPositionMapper


class BybitBroker(Broker):

    def __init__(
        self,
        client: BybitClient,
        order_mapper: BybitOrderMapper,
        position_mapper: BybitPositionMapper,
        category: str,
        symbol: str,
    ):
        self._client = client
        self._order_mapper = order_mapper
        self._position_mapper = position_mapper
        self._category = category
        self._symbol = symbol

    def open_position(
        self,
        request: TradeRequest,
    ) -> Position:

        order = self._order_mapper.to_order_request(
            request,
        )

        response = self._client.place_order(
            category=self._category,
            **order,
        )

        if response["retCode"] != 0:
            raise OrderRejectedError(
                f'Bybit error {response["retCode"]}: {response["retMsg"]}'
            )

        result = response.get("result", {})

        if "orderId" not in result:
            raise BrokerError(
                "Bybit did not return orderId."
            )

        positions = self.get_positions()

        if not positions:
            raise BrokerError(
                "Position was not found after order execution."
            )

        return positions[0]

    def close_position(
        self,
        position: Position,
    ) -> None:

        order = self._order_mapper.to_close_order_request(
            position,
        )

        response = self._client.place_order(
            category=self._category,
            **order,
        )

        if response["retCode"] != 0:
            raise OrderRejectedError(
                f'Bybit error {response["retCode"]}: {response["retMsg"]}'
            )

        result = response.get("result", {})

        if "orderId" not in result:
            raise BrokerError(
                "Bybit did not return orderId."
            )

    def get_positions(
        self,
    ) -> list[Position]:

        response = self._client.get_positions(
            category=self._category,
            symbol=self._symbol,
        )

        if response["retCode"] != 0:
            raise BrokerError(
                f'Bybit error {response["retCode"]}: {response["retMsg"]}'
            )

        positions: list[Position] = []

        for item in response["result"]["list"]:

            if float(item["size"]) == 0:
                continue

            positions.append(
                self._position_mapper.from_position(
                    item,
                )
            )

        return positions