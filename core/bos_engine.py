from core.bos import BOS
from core.bos_type import BOSType
from core.market_structure_state import MarketStructureState


class BOSEngine:

    def detect(
        self,
        state: MarketStructureState,
    ) -> BOS | None:

        if (
            state.previous_hh is not None
            and state.last_hh is not None
            and state.last_hh.price > state.previous_hh.price
        ):
            return BOS(
                index=state.last_hh.index,
                timestamp=state.last_hh.timestamp,
                price=state.last_hh.price,
                type=BOSType.BULLISH,
            )

        if (
            state.previous_ll is not None
            and state.last_ll is not None
            and state.last_ll.price < state.previous_ll.price
        ):
            return BOS(
                index=state.last_ll.index,
                timestamp=state.last_ll.timestamp,
                price=state.last_ll.price,
                type=BOSType.BEARISH,
            )

        return None