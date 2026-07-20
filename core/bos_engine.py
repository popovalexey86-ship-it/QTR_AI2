from core.bos import BOS
from core.bos_type import BOSType
from core.market_data import MarketData
from core.market_structure_state import MarketStructureState


class BOSEngine:

    def detect(
        self,
        state: MarketStructureState,
        market_data: MarketData,
    ) -> BOS | None:

        last_close = market_data.last.close

        # Bullish BOS
        if (
            state.last_hh is not None
            and state.last_broken_hh != state.last_hh
            and last_close > state.last_hh.price
        ):
            state.last_broken_hh = state.last_hh
            

            return BOS(
                index=state.last_hh.index,
                timestamp=market_data.last.timestamp,
                price=state.last_hh.price,
                type=BOSType.BULLISH,
            )

        # Bearish BOS
        if (
            state.last_ll is not None
            and state.last_broken_ll != state.last_ll
            and last_close < state.last_ll.price
        ):
            state.last_broken_ll = state.last_ll
            

            return BOS(
                index=state.last_ll.index,
                timestamp=market_data.last.timestamp,
                price=state.last_ll.price,
                type=BOSType.BEARISH,
            )
        
        return None