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
    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    def __post_init__(self) -> None:
        if self.telegram_enabled and (
            not self.telegram_bot_token
            or not self.telegram_bot_token.strip()
            or not self.telegram_chat_id
            or not self.telegram_chat_id.strip()
        ):
            raise ValueError(
                "Telegram bot token and chat ID are required when Telegram is enabled."
            )

    @classmethod
    def load(cls) -> "Config":

        load_dotenv()

        trade_journal_path = (
            os.getenv("TRADE_JOURNAL_PATH") or "data/trades.csv"
        )
        telegram_enabled = (
            os.getenv("TELEGRAM_ENABLED", "false").strip().lower()
            == "true"
        )
        telegram_bot_token = (
            os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or None
        )
        telegram_chat_id = (
            os.getenv("TELEGRAM_CHAT_ID", "").strip() or None
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
            telegram_enabled=telegram_enabled,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
        )
