from core.bos import BOS
from core.choch import CHOCH
from core.logger import logger
from core.market_structure_state import MarketStructureState
from core.setup import Setup
from core.trend import Trend


class SetupEngine:

    def detect(
        self,
        state: MarketStructureState,
    ) -> Setup | None:
        

        #
        # Во флэте сделки не ищем
        #
        if state.trend == Trend.RANGE:
            return None

        #
        # Определяем последнее структурное событие
        #
        latest_event: BOS | CHOCH | None = None

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
            return None

        #
        # Стоп по структуре рынка
        #
        if state.trend == Trend.BULLISH:

            if state.last_hl is None:
                return None

            stop_loss = state.last_hl.price

            #
            # Стоп обязан быть ниже входа
            #
            if stop_loss >= latest_event.price:
                return None

        elif state.trend == Trend.BEARISH:

            if state.last_lh is None:
                return None

            stop_loss = state.last_lh.price

            #
            # Стоп обязан быть выше входа
            #
            if stop_loss <= latest_event.price:
                return None

        else:
            return None

        #
        # Формируем сетап
        #
        logger.debug(
            "Setup diagnostics | trend=%s entry=%s last_hl=%s "
            "last_lh=%s stop=%s",
            state.trend,
            latest_event.price,
            state.last_hl,
            state.last_lh,
            stop_loss,
        )

        return Setup(
            index=latest_event.index,
            timestamp=latest_event.timestamp,
            trend=state.trend,
            entry=latest_event.price,
            stop_loss=stop_loss,
        )
