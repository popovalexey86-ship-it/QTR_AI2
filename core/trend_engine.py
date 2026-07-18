from core.bos_type import BOSType
from core.choch_type import CHOCHType
from core.market_structure_state import MarketStructureState
from core.trend import Trend


class TrendEngine:

    def update(
        self,
        state: MarketStructureState,
    ) -> None:

        latest_event = None

        if state.last_bos is not None:
            latest_event = state.last_bos

        if (
            state.last_choch is not None
            and (
                latest_event is None
                or state.last_choch.index > latest_event.index
            )
        ):
            latest_event = state.last_choch

        if latest_event is None:
            return

        if latest_event.type in (BOSType.BULLISH, CHOCHType.BULLISH):
            state.trend = Trend.BULLISH

        elif latest_event.type in (BOSType.BEARISH, CHOCHType.BEARISH):
            state.trend = Trend.BEARISH