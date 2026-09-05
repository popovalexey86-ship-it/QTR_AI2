from dataclasses import dataclass
from enum import Enum

from core.bos import BOS
from core.bos_type import BOSType
from core.choch import CHOCH
from core.choch_type import CHOCHType
from core.market_data import MarketData
from core.market_structure_state import MarketStructureState
from strategies.qtr_long.displacement import LongDisplacement


class LongStructureShiftType(Enum):
    MSS = "mss"
    BOS = "bos"


@dataclass(frozen=True, slots=True)
class LongStructureShift:
    """Bullish 5m structural confirmation after displacement."""

    type: LongStructureShiftType
    index: int
    price: float


class LongStructureShiftEngine:
    """Confirm bullish 5m MSS/BOS after displacement.

    QTR Long requires structural confirmation to be created no earlier than the
    displacement candle and within a short execution window. A bullish CHOCH is
    treated as MSS; a bullish BOS is continuation confirmation. Bearish events
    never create SHORT permission and are ignored by this LONG-only engine.

    ``CHOCH.index`` and ``BOS.index`` identify the structural swing that was
    broken, not the candle that confirmed the break. Execution chronology must
    therefore be resolved from the event timestamp back to the 5m MarketData
    candle index before applying the displacement window.
    """

    def __init__(self, *, max_candles_after_displacement: int = 3) -> None:
        if max_candles_after_displacement < 0:
            raise ValueError("max_candles_after_displacement must be >= 0")
        self._max_candles_after_displacement = max_candles_after_displacement

    def confirm(
        self,
        state: MarketStructureState | None,
        displacement: LongDisplacement,
        market_data: MarketData,
    ) -> LongStructureShift | None:
        if state is None:
            return None

        candidates: list[LongStructureShift] = []

        choch = state.last_choch
        if choch is not None and choch.type == CHOCHType.BULLISH:
            confirmation_index = self._confirmation_index(market_data, choch.timestamp)
            if confirmation_index is not None and self._is_in_window(
                confirmation_index,
                displacement,
            ):
                candidates.append(
                    LongStructureShift(
                        type=LongStructureShiftType.MSS,
                        index=confirmation_index,
                        price=choch.price,
                    )
                )

        bos = state.last_bos
        if bos is not None and bos.type == BOSType.BULLISH:
            confirmation_index = self._confirmation_index(market_data, bos.timestamp)
            if confirmation_index is not None and self._is_in_window(
                confirmation_index,
                displacement,
            ):
                candidates.append(
                    LongStructureShift(
                        type=LongStructureShiftType.BOS,
                        index=confirmation_index,
                        price=bos.price,
                    )
                )

        if not candidates:
            return None

        # Prefer the earliest valid structural confirmation after displacement.
        # If MSS and BOS share a confirmation candle, MSS is the more
        # conservative first evidence of a reversal and therefore wins the tie.
        return min(
            candidates,
            key=lambda item: (
                item.index,
                0 if item.type == LongStructureShiftType.MSS else 1,
            ),
        )

    def _is_in_window(self, event_index: int, displacement: LongDisplacement) -> bool:
        delta = event_index - displacement.candle.index
        return 0 <= delta <= self._max_candles_after_displacement

    @staticmethod
    def _confirmation_index(market_data: MarketData, timestamp) -> int | None:
        for candle in reversed(market_data.candles):
            if candle.timestamp == timestamp:
                return candle.index
        return None
