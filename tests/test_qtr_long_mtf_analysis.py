from datetime import UTC, datetime, timedelta

from backtesting.qtr_long_mtf_analysis import QTRLongMTFAnalysisCoordinator
from core.analysis_context import AnalysisContext
from core.candle import Candle
from core.market_data import MarketData
from strategies.qtr_long.timeframe_context import QTRLongTimeframeContext


BASE = datetime(2026, 1, 1, tzinfo=UTC)


class RecordingAnalyzer:
    def __init__(self) -> None:
        self.calls: list[MarketData] = []

    def analyze(self, market_data: MarketData) -> AnalysisContext:
        self.calls.append(market_data)
        return AnalysisContext(market_data=market_data)


def _market_data(*, timeframe: str, timestamp: datetime, index: int) -> MarketData:
    candle = Candle(
        timestamp=timestamp,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1.0,
        index=index,
    )
    return MarketData(
        symbol="BTCUSDT",
        timeframe=timeframe,
        candles=[candle],
        loaded_at=timestamp,
    )


def _context(
    *,
    execution_timestamp: datetime,
    execution_index: int,
    setup_timestamp: datetime = BASE,
    setup_index: int = 0,
    structure_timestamp: datetime = BASE,
    structure_index: int = 0,
    narrative_timestamp: datetime = BASE,
    narrative_index: int = 0,
) -> QTRLongTimeframeContext:
    return QTRLongTimeframeContext(
        execution_5m=_market_data(
            timeframe="5",
            timestamp=execution_timestamp,
            index=execution_index,
        ),
        setup_15m=_market_data(
            timeframe="15",
            timestamp=setup_timestamp,
            index=setup_index,
        ),
        structure_1h=_market_data(
            timeframe="60",
            timestamp=structure_timestamp,
            index=structure_index,
        ),
        narrative_4h=_market_data(
            timeframe="240",
            timestamp=narrative_timestamp,
            index=narrative_index,
        ),
        as_of=execution_timestamp + timedelta(minutes=5),
    )


def _coordinator() -> tuple[
    QTRLongMTFAnalysisCoordinator,
    RecordingAnalyzer,
    RecordingAnalyzer,
    RecordingAnalyzer,
    RecordingAnalyzer,
]:
    execution = RecordingAnalyzer()
    setup = RecordingAnalyzer()
    structure = RecordingAnalyzer()
    narrative = RecordingAnalyzer()
    coordinator = QTRLongMTFAnalysisCoordinator(
        execution_5m=execution,
        setup_15m=setup,
        structure_1h=structure,
        narrative_4h=narrative,
    )
    return coordinator, execution, setup, structure, narrative


def test_analyzes_all_layers_on_first_context() -> None:
    coordinator, execution, setup, structure, narrative = _coordinator()

    result = coordinator.analyze(
        _context(execution_timestamp=BASE + timedelta(hours=4), execution_index=48)
    )

    assert len(execution.calls) == 1
    assert len(setup.calls) == 1
    assert len(structure.calls) == 1
    assert len(narrative.calls) == 1
    assert result.execution_5m.market_data.timeframe == "5"
    assert result.setup_15m.market_data.timeframe == "15"
    assert result.structure_1h.market_data.timeframe == "60"
    assert result.narrative_4h.market_data.timeframe == "240"


def test_reuses_unchanged_higher_timeframe_analysis() -> None:
    coordinator, execution, setup, structure, narrative = _coordinator()

    first = _context(
        execution_timestamp=BASE + timedelta(hours=4),
        execution_index=48,
    )
    second = _context(
        execution_timestamp=BASE + timedelta(hours=4, minutes=5),
        execution_index=49,
    )

    first_result = coordinator.analyze(first)
    second_result = coordinator.analyze(second)

    assert len(execution.calls) == 2
    assert len(setup.calls) == 1
    assert len(structure.calls) == 1
    assert len(narrative.calls) == 1
    assert second_result.setup_15m is first_result.setup_15m
    assert second_result.structure_1h is first_result.structure_1h
    assert second_result.narrative_4h is first_result.narrative_4h


def test_refreshes_only_higher_layer_whose_terminal_candle_advanced() -> None:
    coordinator, execution, setup, structure, narrative = _coordinator()

    coordinator.analyze(
        _context(execution_timestamp=BASE + timedelta(hours=4), execution_index=48)
    )
    result = coordinator.analyze(
        _context(
            execution_timestamp=BASE + timedelta(hours=4, minutes=5),
            execution_index=49,
            setup_timestamp=BASE + timedelta(minutes=15),
            setup_index=1,
        )
    )

    assert len(execution.calls) == 2
    assert len(setup.calls) == 2
    assert len(structure.calls) == 1
    assert len(narrative.calls) == 1
    assert result.setup_15m.market_data.last.timestamp == BASE + timedelta(minutes=15)
