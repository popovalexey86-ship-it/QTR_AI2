from infrastructure.config import Config

from infrastructure.bybit.bybit_client import BybitClient
from infrastructure.bybit.bybit_collector import BybitCollector
from infrastructure.bybit.bybit_broker import BybitBroker
from infrastructure.bybit.bybit_order_mapper import BybitOrderMapper
from infrastructure.bybit.bybit_position_mapper import BybitPositionMapper


class Container:

    def __init__(self):

        self.config = Config.load()

        self.client = BybitClient(self.config)

        self.order_mapper = BybitOrderMapper()
        self.position_mapper = BybitPositionMapper()

        self.collector = BybitCollector(
            client=self.client,
            category="linear",
            symbol="BTCUSDT",
            interval="15",
        )

        self.broker = BybitBroker(
            client=self.client,
            order_mapper=self.order_mapper,
            position_mapper=self.position_mapper,
            category="linear",
            symbol="BTCUSDT",
        )