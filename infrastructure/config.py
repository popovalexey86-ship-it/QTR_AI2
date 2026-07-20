from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Config:
    bybit_api_key: str
    bybit_api_secret: str
    bybit_testnet: bool
    trade_journal_path: Path

    @classmethod
    def load(cls) -> "Config":

        load_dotenv()

        trade_journal_path = (
            os.getenv("TRADE_JOURNAL_PATH") or "data/trades.csv"
        )

        return cls(
            bybit_api_key=os.getenv("BYBIT_API_KEY", ""),
            bybit_api_secret=os.getenv("BYBIT_API_SECRET", ""),
            bybit_testnet=os.getenv(
                "BYBIT_TESTNET",
                "False",
            ).lower()
            == "true",
            trade_journal_path=Path(trade_journal_path),
        )
