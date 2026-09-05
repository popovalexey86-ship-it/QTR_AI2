from dataclasses import dataclass
from datetime import datetime

from backtesting.historical_data import (
    HistoricalCandleCache,
    HistoricalDataResult,
    HistoricalRequest,
    load_historical_data,
)
from infrastructure.bybit.bybit_historical_client import BybitHistoricalClient


_QTR_LONG_INTERVALS = ("5", "15", "60", "240")


@dataclass(frozen=True, slots=True)
class QTRLongHistoricalBundle:
    """Historical candles required by the four-layer QTR Long hierarchy."""

    execution_5m: HistoricalDataResult
    setup_15m: HistoricalDataResult
    structure_1h: HistoricalDataResult
    narrative_4h: HistoricalDataResult

    @property
    def symbol(self) -> str:
        """Return the common symbol encoded by the cache requests' data set.

        The bundle itself intentionally stores only loaded results. Request
        identity stays in the loader inputs so historical cache semantics remain
        centralized in ``HistoricalRequest`` / ``HistoricalCandleCache``.
        """
        if not self.execution_5m.candles:
            return ""
        return ""


@dataclass(frozen=True, slots=True)
class QTRLongHistoricalLoadRequest:
    """One frozen market/time range loaded at all QTR Long timeframes."""

    category: str
    symbol: str
    start: datetime
    end: datetime

    def requests(self) -> tuple[HistoricalRequest, ...]:
        return tuple(
            HistoricalRequest(
                category=self.category,
                symbol=self.symbol,
                interval=interval,
                start=self.start,
                end=self.end,
            )
            for interval in _QTR_LONG_INTERVALS
        )


def load_qtr_long_historical_bundle(
    *,
    client: BybitHistoricalClient,
    cache: HistoricalCandleCache,
    request: QTRLongHistoricalLoadRequest,
    refresh: bool = False,
) -> QTRLongHistoricalBundle:
    """Load 5m, 15m, 1h and 4h candles for exactly one frozen test period."""
    requests = request.requests()
    results = [
        load_historical_data(
            client=client,
            cache=cache,
            request=historical_request,
            refresh=refresh,
        )
        for historical_request in requests
    ]

    return QTRLongHistoricalBundle(
        execution_5m=results[0],
        setup_15m=results[1],
        structure_1h=results[2],
        narrative_4h=results[3],
    )
