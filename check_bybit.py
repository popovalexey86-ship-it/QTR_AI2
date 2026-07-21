from infrastructure.bybit.bybit_client import BybitClient
from infrastructure.config import Config


def main() -> None:
    client = BybitClient(Config.load())

    print(client.get_server_time())


if __name__ == "__main__":
    main()
