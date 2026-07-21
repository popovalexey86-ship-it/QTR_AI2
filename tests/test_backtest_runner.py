from datetime import UTC, datetime, timedelta

import pytest

from backtesting.backtest_runner import BacktestInputError, BacktestRunner
from core.analysis_context import AnalysisContext
from core.candle import Candle
from core.decision_engine import DecisionEngine
from core.market_data import MarketData
from core.risk_manager import RiskManager
from core.setup import Setup
from core.trend import Trend
from strategies.strategy import Strategy


START = datetime(2025, 1, 1, tzinfo=UTC)


class ScriptedStrategy(Strategy):
    def __init__(self, setups: list[Setup | None]) -> None:
        self._setups = setups
        self.timestamps: list[datetime] = []
        self._calls = 0

    def analyze(self, market_data: MarketData) -> AnalysisContext:
        self.timestamps.append(market_data.last.timestamp)
        setup = (
            self._setups[self._calls]
            if self._calls < len(self._setups)
            else None
        )
        self._calls += 1
        return AnalysisContext(market_data=market_data, setup=setup)


def candle(
    minute: int,
    *,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.0,
) -> Candle:
    return Candle(
        timestamp=START + timedelta(minutes=minute),
        open=100.0,
        high=high,
        low=low,
        close=close,
        volume=1.0,
        index=minute,
    )


def snapshots(
    candles: list[Candle],
    symbol: str = "BTCUSDT",
) -> tuple[MarketData, ...]:
    return tuple(
        MarketData(
            symbol=symbol,
            timeframe="1m",
            candles=list(candles[: index + 1]),
            loaded_at=item.timestamp,
        )
        for index, item in enumerate(candles)
    )


def setup(
    trend: Trend = Trend.BULLISH,
    *,
    timestamp: datetime = START,
    entry: float = 100.0,
    stop_loss: float | None = None,
) -> Setup:
    normalized_stop = (
        stop_loss
        if stop_loss is not None
        else (95.0 if trend == Trend.BULLISH else 105.0)
    )
    return Setup(
        index=0,
        timestamp=timestamp,
        trend=trend,
        entry=entry,
        stop_loss=normalized_stop,
    )


def runner(
    strategy: Strategy,
    symbol: str = "BTCUSDT",
    pending_entry_ttl_candles: int = 4,
) -> BacktestRunner:
    return BacktestRunner(
        symbol=symbol,
        strategy=strategy,
        decision_engine=DecisionEngine(),
        risk_manager=RiskManager(risk_reward=2.0),
        pending_entry_ttl_candles=pending_entry_ttl_candles,
    )


def test_snapshots_are_processed_in_chronological_order():
    strategy = ScriptedStrategy([None, None, None])
    history = snapshots([candle(1), candle(2), candle(3)])

    result = runner(strategy).run(iter(history))

    assert strategy.timestamps == [item.last.timestamp for item in history]
    assert result.candles_processed == 3


def test_empty_history_is_rejected():
    with pytest.raises(BacktestInputError, match="cannot be empty"):
        runner(ScriptedStrategy([])).run(())


def test_runner_delegates_pending_ttl_validation() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        runner(ScriptedStrategy([]), pending_entry_ttl_candles=True)


def test_duplicate_snapshot_timestamp_is_rejected():
    duplicate = candle(1)
    history = (
        MarketData("BTCUSDT", "1m", [duplicate]),
        MarketData("BTCUSDT", "1m", [duplicate]),
    )

    with pytest.raises(BacktestInputError, match="Duplicate snapshot timestamp"):
        runner(ScriptedStrategy([])).run(history)


def test_mixed_symbols_are_rejected():
    history = (
        MarketData("BTCUSDT", "1m", [candle(1)]),
        MarketData("ETHUSDT", "1m", [candle(2)]),
    )

    with pytest.raises(BacktestInputError, match="exactly one symbol"):
        runner(ScriptedStrategy([])).run(history)


def test_configured_single_symbol_is_used_for_simulated_fills():
    result = runner(
        ScriptedStrategy([setup(), None]),
        symbol="ETHUSDT",
    ).run(
        snapshots(
            [candle(1), candle(2, high=111.0)],
            symbol="ETHUSDT",
        )
    )

    assert result.symbol == "ETHUSDT"
    assert result.completed_trades[0].symbol == "ETHUSDT"


def test_unsorted_snapshots_are_rejected():
    history = (
        MarketData("BTCUSDT", "1m", [candle(2)]),
        MarketData("BTCUSDT", "1m", [candle(1)]),
    )

    with pytest.raises(BacktestInputError, match="sorted chronologically"):
        runner(ScriptedStrategy([])).run(history)


def test_unsorted_candles_inside_snapshot_are_rejected():
    history = (
        MarketData("BTCUSDT", "1m", [candle(2), candle(1)]),
    )

    with pytest.raises(BacktestInputError, match="not chronological"):
        runner(ScriptedStrategy([])).run(history)


def test_zero_trade_result():
    result = runner(ScriptedStrategy([None, None])).run(
        snapshots([candle(1), candle(2)])
    )

    assert result.total_trades == 0
    assert result.winning_trades == 0
    assert result.losing_trades == 0
    assert result.win_rate == 0.0
    assert result.gross_profit == 0.0
    assert result.gross_loss == 0.0
    assert result.net_pnl == 0.0
    assert result.has_open_position is False
    assert result.completed_trades == ()


def test_final_active_pending_entry_is_reported_without_artificial_fill():
    result = runner(ScriptedStrategy([setup()])).run(
        snapshots([candle(1)])
    )

    assert result.total_trades == 0
    assert result.has_open_position is False
    assert result.has_pending_entry is True
    assert result.final_pending_entry is not None
    assert "Final pending entry: ACTIVE" in result.summary()


def test_unclosed_filled_position_is_reported_independently() -> None:
    result = runner(ScriptedStrategy([setup(), None])).run(
        snapshots([candle(1), candle(2)])
    )

    assert result.total_trades == 0
    assert result.has_open_position is True
    assert result.has_pending_entry is False
    assert result.final_pending_entry is None


def test_invalid_pending_entry_is_counted_and_does_not_open_position():
    invalid_setup = setup(stop_loss=105.0)
    result = runner(ScriptedStrategy([invalid_setup])).run(
        snapshots([candle(1, close=111.0, high=112.0, low=110.0)])
    )

    assert result.rejected_orders == 1
    assert result.total_trades == 0
    assert result.has_open_position is False


def test_one_winning_trade_has_consistent_metrics():
    result = runner(ScriptedStrategy([setup(), None])).run(
        snapshots([candle(1), candle(2, high=111.0, low=99.0)])
    )

    assert result.total_trades == 1
    assert result.winning_trades == 1
    assert result.losing_trades == 0
    assert result.win_rate == 1.0
    assert result.gross_profit == pytest.approx(0.1)
    assert result.gross_loss == 0.0
    assert result.net_pnl == pytest.approx(0.1)
    assert result.net_pnl == pytest.approx(
        result.gross_profit - result.gross_loss
    )
    assert result.has_open_position is False


def test_one_losing_trade_has_consistent_metrics():
    result = runner(ScriptedStrategy([setup(), None])).run(
        snapshots([candle(1), candle(2, high=101.0, low=94.0)])
    )

    assert result.total_trades == 1
    assert result.winning_trades == 0
    assert result.losing_trades == 1
    assert result.win_rate == 0.0
    assert result.gross_profit == 0.0
    assert result.gross_loss == pytest.approx(0.05)
    assert result.net_pnl == pytest.approx(-0.05)
    assert result.net_pnl == pytest.approx(
        result.gross_profit - result.gross_loss
    )


def test_synthetic_tickets_are_stable_and_ordered():
    second_setup = setup(timestamp=START + timedelta(minutes=3))
    result = runner(
        ScriptedStrategy([setup(), None, second_setup, None])
    ).run(
        snapshots(
            [
                candle(1),
                candle(2, high=111.0),
                candle(3),
                candle(4, high=111.0),
            ]
        )
    )

    assert [trade.ticket for trade in result.completed_trades] == [
        "SIM-000001",
        "SIM-000002",
    ]


def test_backtest_does_not_use_bybit_or_telegram(monkeypatch):
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(
        "infrastructure.telegram_notifier.TelegramNotifier._send",
        fail_network,
    )
    monkeypatch.setattr(
        "infrastructure.bybit.bybit_client.BybitClient.get_server_time",
        fail_network,
    )

    result = runner(ScriptedStrategy([None])).run(snapshots([candle(1)]))

    assert result.total_trades == 0


def test_signal_candle_never_fills_pending_entry() -> None:
    result = runner(ScriptedStrategy([setup()])).run(
        snapshots([candle(1, high=111.0, low=94.0)])
    )

    assert result.total_trades == 0
    assert result.has_open_position is False
    assert result.has_pending_entry is True
    assert result.filled_entries == 0


def test_pending_entry_can_fill_only_on_next_candle() -> None:
    result = runner(ScriptedStrategy([setup(), None])).run(
        snapshots([candle(1, high=111.0, low=94.0), candle(2)])
    )

    assert result.filled_entries == 1
    assert result.has_open_position is True
    assert result.has_pending_entry is False


@pytest.mark.parametrize(
    ("high", "low", "expected_exit"),
    [(101.0, 94.0, 95.0), (111.0, 99.0, 110.0)],
)
def test_same_candle_marketable_fill_and_close_is_journaled_once(
    high: float,
    low: float,
    expected_exit: float,
) -> None:
    result = runner(ScriptedStrategy([setup(), None])).run(
        snapshots([candle(1), candle(2, high=high, low=low)])
    )

    assert result.total_trades == 1
    assert len(result.completed_trades) == 1
    assert result.completed_trades[0].exit == expected_exit
    assert result.filled_entries == 1


def test_duplicate_setup_is_suppressed_after_completed_trade() -> None:
    repeated_setup = setup()
    result = runner(
        ScriptedStrategy([repeated_setup, repeated_setup, repeated_setup])
    ).run(
        snapshots(
            [
                candle(1),
                candle(2, high=111.0),
                candle(3),
            ]
        )
    )

    assert result.total_trades == 1
    assert result.submitted_entries == 1
    assert result.has_pending_entry is False


def test_expired_setup_is_suppressed_but_new_setup_can_submit() -> None:
    first_setup = setup(entry=90.0, stop_loss=85.0)
    new_setup = setup(
        timestamp=START + timedelta(minutes=5),
        entry=91.0,
        stop_loss=86.0,
    )
    result = runner(
        ScriptedStrategy([first_setup, new_setup]),
        pending_entry_ttl_candles=4,
    ).run(
        snapshots([candle(index) for index in range(1, 6)])
    )

    assert result.expired_entries == 1
    assert result.submitted_entries == 2
    assert result.has_pending_entry is True
    assert result.final_pending_entry is not None
    assert result.final_pending_entry.request.entry == 91.0


def test_same_setup_is_not_recreated_after_ttl_expiry() -> None:
    repeated_setup = setup(entry=90.0, stop_loss=85.0)
    result = runner(
        ScriptedStrategy([repeated_setup, repeated_setup]),
        pending_entry_ttl_candles=4,
    ).run(
        snapshots([candle(index) for index in range(1, 6)])
    )

    assert result.expired_entries == 1
    assert result.submitted_entries == 1
    assert result.has_pending_entry is False


def test_repeated_backtests_are_deterministic() -> None:
    history = snapshots([candle(1), candle(2, high=111.0)])

    first = runner(ScriptedStrategy([setup(), None])).run(history)
    second = runner(ScriptedStrategy([setup(), None])).run(history)

    assert first == second
