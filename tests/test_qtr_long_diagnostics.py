import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backtesting.qtr_long_diagnostics import (
    LongDiagnosticsError,
    write_qtr_long_diagnostics_csv,
)
from core.decision import Decision
from core.trade import Trade
from strategies.qtr_long.diagnostics import LongSignalDiagnostic


def _signal() -> LongSignalDiagnostic:
    timestamp = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    return LongSignalDiagnostic(
        signal_timestamp=timestamp,
        setup_type="sweep_reclaim_order_block",
        score_total=85,
        score_grade="long",
        score_structure=25,
        score_liquidity=20,
        score_order_block=15,
        score_fvg=5,
        score_momentum=10,
        score_volume=5,
        score_location=5,
        sweep_timestamp=timestamp - timedelta(minutes=30),
        sweep_price=100.0,
        sweep_extreme=99.0,
        sweep_reclaim_close=100.5,
        order_block_timestamp=timestamp - timedelta(minutes=15),
        order_block_status="fresh",
        order_block_low=100.0,
        order_block_high=102.0,
        order_block_midpoint=101.0,
        entry=101.0,
        stop_loss=99.0,
    )


def _trade(*, decision: Decision = Decision.BUY, pnl: float = 4.0) -> Trade:
    opened_at = datetime(2025, 1, 1, 12, 15, tzinfo=UTC)
    return Trade(
        ticket="SIM-000001",
        symbol="BTCUSDT",
        decision=decision,
        entry=101.0,
        exit=105.0 if pnl > 0 else 99.0,
        volume=1.0,
        pnl=pnl,
        fees=0.0,
        opened_at=opened_at,
        closed_at=opened_at + timedelta(minutes=45),
    )


def test_write_qtr_long_diagnostics_csv(tmp_path: Path) -> None:
    output = tmp_path / "diagnostics.csv"

    result = write_qtr_long_diagnostics_csv(
        output,
        signals=(_signal(),),
        trades=(_trade(),),
    )

    assert result == output
    with output.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 1
    assert rows[0]["decision"] == Decision.BUY.value
    assert rows[0]["score_total"] == "85"
    assert rows[0]["result_r"] == "2.000000"
    assert rows[0]["outcome"] == "WIN"


def test_diagnostics_reject_signal_trade_count_mismatch(tmp_path: Path) -> None:
    with pytest.raises(LongDiagnosticsError, match="accepted_signals=1 completed_trades=0"):
        write_qtr_long_diagnostics_csv(
            tmp_path / "diagnostics.csv",
            signals=(_signal(),),
            trades=(),
        )


def test_diagnostics_reject_non_buy_trade(tmp_path: Path) -> None:
    with pytest.raises(LongDiagnosticsError, match="invariant violated"):
        write_qtr_long_diagnostics_csv(
            tmp_path / "diagnostics.csv",
            signals=(_signal(),),
            trades=(_trade(decision=Decision.SELL),),
        )
