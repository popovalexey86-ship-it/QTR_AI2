from pathlib import Path
from unittest.mock import Mock

import pytest

from infrastructure.bybit.bybit_entry_order_mapper import BybitEntryOrderMapper
from infrastructure.bybit.bybit_entry_order_snapshot_mapper import (
    BybitEntryOrderSnapshotMapper,
)
import infrastructure.bybit.bybit_client as client_module
from infrastructure.config import Config
from infrastructure.container import Container


@pytest.mark.parametrize("testnet", [True, False])
def test_container_injects_pending_dependencies_without_api_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    testnet: bool,
) -> None:
    session = Mock()
    http_factory = Mock(return_value=session)
    monkeypatch.setattr(client_module, "HTTP", http_factory)
    state_path = tmp_path / "runtime" / "pending.json"
    config = Config(
        bybit_api_key="test-key",
        bybit_api_secret="test-secret",
        bybit_testnet=testnet,
        trade_journal_path=tmp_path / "trades.csv",
        bybit_pending_entry_state_path=state_path,
    )

    container = Container(config)

    assert isinstance(container.entry_order_mapper, BybitEntryOrderMapper)
    assert isinstance(
        container.entry_snapshot_mapper,
        BybitEntryOrderSnapshotMapper,
    )
    assert container.broker._entry_order_mapper is container.entry_order_mapper
    assert (
        container.broker._entry_snapshot_mapper
        is container.entry_snapshot_mapper
    )
    assert container.broker._pending_entry_store is container.pending_entry_store
    assert container.pending_entry_store._path == state_path
    assert container.collector._category == "linear"
    assert container.collector._symbol == "BTCUSDT"
    assert container.collector._interval == "15"
    assert container.client.is_testnet is testnet
    assert session.mock_calls == []
    assert not state_path.exists()
