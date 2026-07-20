from pathlib import Path

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
