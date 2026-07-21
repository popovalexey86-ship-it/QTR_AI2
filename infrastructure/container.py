from infrastructure.config import Config

from infrastructure.bybit.bybit_client import BybitClient
from infrastructure.bybit.bybit_collector import BybitCollector
from infrastructure.bybit.bybit_broker import BybitBroker
from infrastructure.bybit.bybit_entry_order_mapper import BybitEntryOrderMapper
from infrastructure.bybit.bybit_entry_order_snapshot_mapper import (
    BybitEntryOrderSnapshotMapper,
)
from infrastructure.bybit.bybit_order_mapper import BybitOrderMapper
from infrastructure.bybit.bybit_pending_entry_store import BybitPendingEntryStore
from infrastructure.bybit.bybit_position_mapper import BybitPositionMapper


class Container:

    def __init__(self, config: Config | None = None) -> None:

        self.config = config or Config.load()

        self.client = BybitClient(self.config)

        self.order_mapper = BybitOrderMapper()
        self.position_mapper = BybitPositionMapper()
        self.entry_order_mapper = BybitEntryOrderMapper()
        self.entry_snapshot_mapper = BybitEntryOrderSnapshotMapper()
        self.pending_entry_store = BybitPendingEntryStore(
            self.config.bybit_pending_entry_state_path
        )

        self.collector = BybitCollector(
            client=self.client,
            category="linear",
            symbol="BTCUSDT",
            interval="15",
        )

        self.broker = BybitBroker(
            client=self.client,
            order_mapper=self.order_mapper,
            position_mapper=self.position_mapper,
            entry_order_mapper=self.entry_order_mapper,
            entry_snapshot_mapper=self.entry_snapshot_mapper,
            pending_entry_store=self.pending_entry_store,
            category="linear",
            symbol="BTCUSDT",
        )
