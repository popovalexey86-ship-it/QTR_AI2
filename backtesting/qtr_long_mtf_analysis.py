from dataclasses import dataclass
from typing import Protocol

from core.analysis_context import AnalysisContext
from core.market_data import MarketData
from strategies.qtr_long.timeframe_context import QTRLongTimeframeContext


class MarketAnalyzer(Protocol):
    """Minimal analysis contract used by the QTR Long MTF backtest layer."""

    def analyze(self, market_data: MarketData) -> AnalysisContext:
        ...


@dataclass(frozen=True, slots=True)
class QTRLongMTFAnalysis:
    """Analysis contexts bound to one synchronized QTR Long timeframe context."""

    execution_5m: AnalysisContext
    setup_15m: AnalysisContext
    structure_1h: AnalysisContext
    narrative_4h: AnalysisContext


class QTRLongMTFAnalysisCoordinator:
    """Analyze each timeframe only when its closed candle history advances.

    AnalysisEngine is stateful. Re-running a higher-timeframe engine on the same
    terminal candle at every 5m clock tick can mutate market-structure state more
    than once for identical data. This coordinator therefore caches the latest
    analysis for 15m/1h/4h and refreshes it only when that layer's terminal
    candle changes. The 5m execution layer advances on every emitted context and
    is analyzed every time.
    """

    def __init__(
        self,
        *,
        execution_5m: MarketAnalyzer,
        setup_15m: MarketAnalyzer,
        structure_1h: MarketAnalyzer,
        narrative_4h: MarketAnalyzer,
    ) -> None:
        self._execution_5m_engine = execution_5m
        self._setup_15m_engine = setup_15m
        self._structure_1h_engine = structure_1h
        self._narrative_4h_engine = narrative_4h

        self._setup_15m: AnalysisContext | None = None
        self._structure_1h: AnalysisContext | None = None
        self._narrative_4h: AnalysisContext | None = None

    def analyze(self, context: QTRLongTimeframeContext) -> QTRLongMTFAnalysis:
        execution = self._execution_5m_engine.analyze(context.execution_5m)

        self._setup_15m = self._refresh_if_advanced(
            current=self._setup_15m,
            market_data=context.setup_15m,
            engine=self._setup_15m_engine,
        )
        self._structure_1h = self._refresh_if_advanced(
            current=self._structure_1h,
            market_data=context.structure_1h,
            engine=self._structure_1h_engine,
        )
        self._narrative_4h = self._refresh_if_advanced(
            current=self._narrative_4h,
            market_data=context.narrative_4h,
            engine=self._narrative_4h_engine,
        )

        return QTRLongMTFAnalysis(
            execution_5m=execution,
            setup_15m=self._setup_15m,
            structure_1h=self._structure_1h,
            narrative_4h=self._narrative_4h,
        )

    @staticmethod
    def _refresh_if_advanced(
        *,
        current: AnalysisContext | None,
        market_data: MarketData,
        engine: MarketAnalyzer,
    ) -> AnalysisContext:
        if current is None or current.market_data.last != market_data.last:
            return engine.analyze(market_data)
        return current
