from pprint import pprint

from infrastructure.config import Config
from infrastructure.bybit.bybit_client import BybitClient

config = Config.load()
client = BybitClient(config)

response = client.get_positions(
    category="linear",
    symbol="BTCUSDT",
)

pprint(response)
