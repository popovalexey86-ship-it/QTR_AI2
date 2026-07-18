from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Config:
    bybit_api_key: str
    bybit_api_secret: str
    bybit_testnet: bool

    @classmethod
    def load(cls) -> "Config":

        load_dotenv()

        return cls(
            bybit_api_key=os.getenv("BYBIT_API_KEY", ""),
            bybit_api_secret=os.getenv("BYBIT_API_SECRET", ""),
            bybit_testnet=os.getenv(
                "BYBIT_TESTNET",
                "False",
            ).lower()
            == "true",
        )
