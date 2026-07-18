from infrastructure.bybit.bybit_client import BybitClient

client = BybitClient()

print(client.get_server_time())
