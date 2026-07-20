from core.choch import CHOCH
from core.choch_type import CHOCHType
from core.market_data import MarketData
from core.market_structure_state import MarketStructureState


class CHOCHEngine:

    def detect(
        self,
        state: MarketStructureState,
        market_data: MarketData,
    ) -> CHOCH | None:

        last_close = market_data.last.close

        #
        # Bearish CHOCH
        #
        if (
            state.last_hl is not None
            and state.last_broken_hl != state.last_hl
            and last_close < state.last_hl.price
        ):
            state.last_broken_hl = state.last_hl
           
            return CHOCH(
                index=state.last_hl.index,
                timestamp=market_data.last.timestamp,
                price=state.last_hl.price,
                type=CHOCHType.BEARISH,
            )

        #
        # Bullish CHOCH
        #
        if (
            state.last_lh is not None
            and state.last_broken_lh != state.last_lh
            and last_close > state.last_lh.price
        ):
            state.last_broken_lh = state.last_lh
            

            return CHOCH(
                index=state.last_lh.index,
                timestamp=market_data.last.timestamp,
                price=state.last_lh.price,
                type=CHOCHType.BULLISH,
            )
        
        return None