from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Config:
    bybit_api_key: str = field(repr=False)
    bybit_api_secret: str = field(repr=False)
    bybit_testnet: bool
    trade_journal_path: Path
    bybit_pending_entry_state_path: Path = Path(
        "data/bybit_pending_entry.json"
    )
    pending_entry_ttl_candles: int = 4
    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    def __post_init__(self) -> None:
        state_path_text = str(self.bybit_pending_entry_state_path).strip()
        if not state_path_text or state_path_text == ".":
            raise ValueError("Bybit pending-entry state path cannot be empty.")
        if (
            isinstance(self.pending_entry_ttl_candles, bool)
            or not isinstance(self.pending_entry_ttl_candles, int)
            or self.pending_entry_ttl_candles <= 0
        ):
            raise ValueError(
                "Pending-entry TTL must be a positive integer."
            )
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
        state_path_environment = os.getenv("BYBIT_PENDING_ENTRY_STATE_PATH")
        if state_path_environment is None:
            state_path = "data/bybit_pending_entry.json"
        elif not state_path_environment.strip():
            raise ValueError("Bybit pending-entry state path cannot be empty.")
        else:
            state_path = state_path_environment.strip()

        ttl_environment = os.getenv("PENDING_ENTRY_TTL_CANDLES", "4").strip()
        try:
            pending_entry_ttl_candles = int(ttl_environment)
        except ValueError:
            raise ValueError(
                "Pending-entry TTL must be a positive integer."
            ) from None
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
            bybit_pending_entry_state_path=Path(state_path),
            pending_entry_ttl_candles=pending_entry_ttl_candles,
            telegram_enabled=telegram_enabled,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
        )
