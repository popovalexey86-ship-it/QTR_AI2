from pathlib import Path

import pytest

from infrastructure.config import Config


def test_config_uses_trade_journal_path_from_environment(monkeypatch):
    monkeypatch.setenv("TRADE_JOURNAL_PATH", "temporary/trades.csv")

    config = Config.load()

    assert config.trade_journal_path == Path("temporary/trades.csv")


def test_config_uses_default_trade_journal_path(monkeypatch):
    monkeypatch.setattr("infrastructure.config.load_dotenv", lambda: None)
    monkeypatch.delenv("TRADE_JOURNAL_PATH", raising=False)

    config = Config.load()

    assert config.trade_journal_path == Path("data/trades.csv")


def test_config_preserves_absolute_trade_journal_path(monkeypatch, tmp_path):
    absolute_path = (tmp_path / "trades.csv").resolve()
    monkeypatch.setenv("TRADE_JOURNAL_PATH", str(absolute_path))

    config = Config.load()

    assert config.trade_journal_path == absolute_path


def test_config_uses_default_for_empty_trade_journal_path(monkeypatch):
    monkeypatch.setenv("TRADE_JOURNAL_PATH", "")

    config = Config.load()

    assert config.trade_journal_path == Path("data/trades.csv")


def test_telegram_is_disabled_by_default(monkeypatch):
    monkeypatch.setattr("infrastructure.config.load_dotenv", lambda: None)
    for name in ("TELEGRAM_ENABLED", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(name, raising=False)

    config = Config.load()

    assert config.telegram_enabled is False
    assert config.telegram_bot_token is None
    assert config.telegram_chat_id is None


def test_config_loads_enabled_telegram_settings(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ENABLED", " TrUe ")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", " test-token ")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", " test-chat ")

    config = Config.load()

    assert config.telegram_enabled is True
    assert config.telegram_bot_token == "test-token"
    assert config.telegram_chat_id == "test-chat"


@pytest.mark.parametrize("missing_name", ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"])
def test_enabled_telegram_requires_complete_credentials(monkeypatch, missing_name):
    monkeypatch.setattr("infrastructure.config.load_dotenv", lambda: None)
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "sensitive-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "test-chat")
    monkeypatch.delenv(missing_name, raising=False)

    with pytest.raises(ValueError) as error:
        Config.load()

    assert "sensitive-token" not in str(error.value)


def test_disabled_telegram_allows_missing_credentials(tmp_path):
    config = Config(
        bybit_api_key="key",
        bybit_api_secret="secret",
        bybit_testnet=True,
        trade_journal_path=tmp_path / "trades.csv",
    )

    assert config.telegram_enabled is False
