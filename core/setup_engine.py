from core.bos import BOS
from core.choch import CHOCH
from core.market_structure_state import MarketStructureState
from core.setup import Setup
from core.trend import Trend


class SetupEngine:

    def detect(
        self,
        state: MarketStructureState,
    ) -> Setup | None:

        if state.trend == Trend.RANGE:
            return None

        latest_event: BOS | CHOCH | None = None

        if state.last_bos is not None:
            latest_event = state.last_bos

        if state.last_choch is not None and (
            latest_event is None or state.last_choch.index > latest_event.index
        ):
            latest_event = state.last_choch

        if latest_event is None:
            return None

        return Setup(
            index=latest_event.index,
            timestamp=latest_event.timestamp,
            trend=state.trend,
            entry=latest_event.price,
            stop_loss=latest_event.price,
        )
