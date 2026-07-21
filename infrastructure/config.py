from dataclasses import dataclass, field
import os
import math
from pathlib import Path
import re

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
    trade_symbol: str = "BTCUSDT"
    trade_interval: str = "15"
    trade_volume: float = 0.01
    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    def __post_init__(self) -> None:
        symbol = self.trade_symbol.strip().upper()
        if not symbol or re.fullmatch(r"[A-Z0-9_-]+", symbol) is None:
            raise ValueError("Trade symbol must be non-empty and ASCII-safe.")
        interval = self.trade_interval.strip()
        if (
            not interval.isascii()
            or not interval.isdecimal()
            or int(interval) <= 0
        ):
            raise ValueError(
                "Trade interval must be a positive numeric-minute string."
            )
        if (
            isinstance(self.trade_volume, bool)
            or not isinstance(self.trade_volume, (int, float))
            or not math.isfinite(self.trade_volume)
            or self.trade_volume <= 0
        ):
            raise ValueError("Trade volume must be finite and positive.")
        object.__setattr__(self, "trade_symbol", symbol)
        object.__setattr__(self, "trade_interval", interval)
        object.__setattr__(self, "trade_volume", float(self.trade_volume))
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
        trade_symbol = os.getenv("TRADE_SYMBOL", "BTCUSDT")
        trade_interval = os.getenv("TRADE_INTERVAL", "15")
        trade_volume_environment = os.getenv("TRADE_VOLUME", "0.01").strip()
        try:
            trade_volume = float(trade_volume_environment)
        except ValueError:
            raise ValueError("Trade volume must be finite and positive.") from None
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
            trade_symbol=trade_symbol,
            trade_interval=trade_interval,
            trade_volume=trade_volume,
            telegram_enabled=telegram_enabled,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
        )
