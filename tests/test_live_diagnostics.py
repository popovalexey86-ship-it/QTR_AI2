from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

import main
from core.candle import Candle
from core.market_data import MarketData
from infrastructure.bybit.bybit_preflight import run_bybit_testnet_preflight
import infrastructure.bybit.bybit_client as client_module
from infrastructure.config import Config


def _config(
    tmp_path: Path,
    *,
    bybit_testnet: bool = True,
    bybit_api_key: str = "sensitive-key",
) -> Config:
    return Config(
        bybit_api_key=bybit_api_key,
        bybit_api_secret="sensitive-secret",
        bybit_testnet=bybit_testnet,
        trade_journal_path=tmp_path / "trades.csv",
        bybit_pending_entry_state_path=tmp_path / "state" / "pending.json",
        trade_symbol="BTCUSDT",
        trade_interval="15",
        trade_volume=0.01,
        pending_entry_ttl_candles=4,
    )


def _market_data() -> MarketData:
    return MarketData(
        symbol="BTCUSDT",
        timeframe="15",
        candles=[
            Candle(
                timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=1.0,
            )
        ],
    )


def test_configuration_check_has_zero_network_and_safe_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _config(tmp_path)
    state_path = config.bybit_pending_entry_state_path
    state_path.parent.mkdir(parents=True)
    state_path.write_text("do-not-overwrite", encoding="utf-8")
    session = Mock()
    monkeypatch.setattr(main.Config, "load", Mock(return_value=config))
    monkeypatch.setattr(client_module, "HTTP", Mock(return_value=session))
    monkeypatch.setattr(
        "infrastructure.telegram_notifier.TelegramNotifier._send",
        Mock(side_effect=AssertionError("Telegram call")),
    )

    main.check_live_configuration()

    output = capsys.readouterr().out
    assert "Mode: Bybit Testnet" in output
    assert "Symbol: BTCUSDT" in output
    assert "Interval: 15" in output
    assert "Volume: 0.01" in output
    assert "TTL: 4" in output
    assert "Configuration valid" in output
    assert "sensitive-key" not in output
    assert "sensitive-secret" not in output
    assert session.mock_calls == []
    assert state_path.read_text(encoding="utf-8") == "do-not-overwrite"


def test_configuration_check_rejects_mainnet_and_missing_credentials(
    tmp_path: Path,
) -> None:
    with pytest.raises(main.LiveConfigurationError, match="Testnet"):
        main.validate_live_configuration(_config(tmp_path, bybit_testnet=False))
    with pytest.raises(main.LiveConfigurationError, match="credentials"):
        main.validate_live_configuration(_config(tmp_path, bybit_api_key=""))


def _preflight_container(
    tmp_path: Path,
    *,
    positions: list[object] | None = None,
    owned: int = 0,
    protective: int = 0,
    foreign: int = 0,
    durable_state: object | None = None,
):
    config = _config(tmp_path)
    store = Mock()
    store.load.return_value = durable_state
    collector = Mock()
    collector.collect_completed.return_value = _market_data()
    broker = Mock()
    broker.get_positions.return_value = positions or []
    broker.inspect_active_order_counts.return_value = (
        owned,
        protective,
        foreign,
    )
    client = Mock()
    return SimpleNamespace(
        config=config,
        pending_entry_store=store,
        collector=collector,
        broker=broker,
        client=client,
    )


def test_clean_preflight_is_ready_and_uses_exact_read_only_sequence(
    tmp_path: Path,
) -> None:
    container = _preflight_container(tmp_path)
    parent = Mock()
    parent.attach_mock(container.pending_entry_store.load, "load")
    parent.attach_mock(container.collector.collect_completed, "collect")
    parent.attach_mock(container.broker.get_positions, "positions")
    parent.attach_mock(container.broker.inspect_active_order_counts, "orders")

    report = run_bybit_testnet_preflight(container)

    assert report.ready is True
    assert report.connectivity_ok is True
    assert report.private_api_ok is True
    assert parent.mock_calls == [
        call.load(),
        call.collect(),
        call.positions(),
        call.orders([]),
    ]
    container.client.place_order.assert_not_called()
    container.client.cancel_order.assert_not_called()


@pytest.mark.parametrize(
    ("positions", "owned", "protective", "foreign", "durable", "reason"),
    [
        ([object()], 0, 0, 0, None, "Open position"),
        ([], 1, 0, 0, None, "QTR-owned"),
        ([], 0, 0, 1, None, "Foreign"),
        ([], 0, 0, 0, object(), "Durable"),
    ],
)
def test_preflight_blocking_conditions(
    tmp_path: Path,
    positions: list[object],
    owned: int,
    protective: int,
    foreign: int,
    durable: object | None,
    reason: str,
) -> None:
    container = _preflight_container(
        tmp_path,
        positions=positions,
        owned=owned,
        protective=protective,
        foreign=foreign,
        durable_state=durable,
    )

    report = run_bybit_testnet_preflight(container)

    assert report.ready is False
    assert reason in (report.blocking_reason or "")
    container.client.place_order.assert_not_called()
    container.client.cancel_order.assert_not_called()


def test_protected_position_is_ready_and_summary_separates_orders(
    tmp_path: Path,
) -> None:
    position = object()
    container = _preflight_container(
        tmp_path,
        positions=[position],
        protective=2,
    )

    report = run_bybit_testnet_preflight(container)

    assert report.ready is True
    assert report.open_position_count == 1
    assert report.protective_active_order_count == 2
    assert report.foreign_active_order_count == 0
    assert "Protective orders: 2" in report.summary()
    assert "Foreign/manual active order count: 0" in report.summary()
    container.broker.inspect_active_order_counts.assert_called_once_with(
        [position]
    )


@pytest.mark.parametrize("failure_stage", ["state", "candles", "private"])
def test_preflight_failures_are_safe(
    tmp_path: Path,
    failure_stage: str,
) -> None:
    container = _preflight_container(tmp_path)
    secret_error = RuntimeError("secret=https://signed.example")
    if failure_stage == "state":
        container.pending_entry_store.load.side_effect = secret_error
    elif failure_stage == "candles":
        container.collector.collect_completed.side_effect = secret_error
    else:
        container.broker.get_positions.side_effect = secret_error

    report = run_bybit_testnet_preflight(container)
    output = report.summary()

    assert report.ready is False
    assert "secret" not in output
    assert "signed.example" not in output
    container.client.place_order.assert_not_called()
    container.client.cancel_order.assert_not_called()
