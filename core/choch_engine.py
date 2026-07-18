from core.choch import CHOCH
from core.choch_type import CHOCHType
from core.market_structure_state import MarketStructureState


class CHOCHEngine:

    def detect(
        self,
        state: MarketStructureState,
    ) -> CHOCH | None:

        if (
            state.previous_hl is not None
            and state.last_hl is not None
            and state.last_hl.price < state.previous_hl.price
        ):
            return CHOCH(
                index=state.last_hl.index,
                timestamp=state.last_hl.timestamp,
                price=state.last_hl.price,
                type=CHOCHType.BEARISH,
            )

        if (
            state.previous_lh is not None
            and state.last_lh is not None
            and state.last_lh.price > state.previous_lh.price
        ):
            return CHOCH(
                index=state.last_lh.index,
                timestamp=state.last_lh.timestamp,
                price=state.last_lh.price,
                type=CHOCHType.BULLISH,
            )

        return None
