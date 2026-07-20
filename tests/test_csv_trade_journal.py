from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from core.decision import Decision
from core.trade import Trade
from core.trade_journal import TradeJournalWriteError
import infrastructure.csv_trade_journal as journal_module
from infrastructure.csv_trade_journal import CsvTradeJournal


def make_trade(ticket: str = "trade-1") -> Trade:
    return Trade(
        ticket=ticket,
        symbol="BTCUSDT",
        decision=Decision.BUY,
        entry=100.0,
        exit=105.0,
        volume=0.01,
        pnl=5.0,
        fees=0.1,
        opened_at=datetime(2025, 1, 1, tzinfo=UTC),
        closed_at=datetime(2025, 1, 2, tzinfo=UTC),
    )


def test_creates_csv_header_once_and_round_trips_trade(tmp_path):
    path = tmp_path / "journal" / "trades.csv"
    journal = CsvTradeJournal(path)
    trade = make_trade()

    assert path.read_text(encoding="utf-8").splitlines() == [
        ",".join(CsvTradeJournal.FIELDNAMES)
    ]
    assert journal.add_trade(trade) is True

    reloaded_journal = CsvTradeJournal(path)

    assert reloaded_journal.trades == (trade,)
    assert path.read_text(encoding="utf-8").splitlines().count(
        ",".join(CsvTradeJournal.FIELDNAMES)
    ) == 1


def test_blocks_duplicate_ticket_before_and_after_restart(tmp_path):
    path = tmp_path / "trades.csv"
    trade = make_trade()
    journal = CsvTradeJournal(path)

    assert journal.add_trade(trade) is True
    assert journal.add_trade(trade) is False

    reloaded_journal = CsvTradeJournal(path)

    assert reloaded_journal.add_trade(trade) is False
    assert reloaded_journal.trades == (trade,)


def test_rejects_incompatible_header(tmp_path):
    path = tmp_path / "trades.csv"
    path.write_text("ticket,symbol\n", encoding="utf-8")

    with pytest.raises(ValueError, match="header"):
        CsvTradeJournal(path)


def test_reports_corrupted_row_with_line_number(tmp_path):
    path = tmp_path / "trades.csv"
    path.write_text(
        ",".join(CsvTradeJournal.FIELDNAMES) + "\n"
        "trade-1,BTCUSDT,NOT_A_DECISION,100,105,0.01,5,0.1,"
        "2025-01-01T00:00:00+00:00,2025-01-02T00:00:00+00:00\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="row 2"):
        CsvTradeJournal(path)


@pytest.mark.parametrize("failure_point", ["writerow", "flush", "fsync"])
def test_write_failure_preserves_state_and_allows_retry(
    tmp_path,
    monkeypatch,
    failure_point,
):
    path = tmp_path / "trades.csv"
    journal = CsvTradeJournal(path)
    trade = make_trade()
    original_error = OSError(f"{failure_point} failed")
    file = MagicMock()
    file.__enter__.return_value = file
    writer = Mock()

    if failure_point == "writerow":
        writer.writerow.side_effect = original_error
    elif failure_point == "flush":
        file.flush.side_effect = original_error

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", Mock(return_value=file))
        patch.setattr(
            journal_module.csv,
            "DictWriter",
            Mock(return_value=writer),
        )
        if failure_point == "fsync":
            patch.setattr(journal_module.os, "fsync", Mock(side_effect=original_error))

        with pytest.raises(TradeJournalWriteError) as error_info:
            journal.add_trade(trade)

    assert error_info.value.__cause__ is original_error
    assert str(path) in str(error_info.value)
    assert trade.ticket in str(error_info.value)
    assert journal.trades == ()
    assert journal.add_trade(trade) is True
    assert journal.trades == (trade,)


def test_successful_write_calls_fsync(tmp_path, monkeypatch):
    journal = CsvTradeJournal(tmp_path / "trades.csv")
    fsync = Mock()
    monkeypatch.setattr(journal_module.os, "fsync", fsync)

    assert journal.add_trade(make_trade()) is True

    fsync.assert_called_once()


def test_rejects_duplicate_ticket_inside_existing_csv(tmp_path):
    path = tmp_path / "trades.csv"
    journal = CsvTradeJournal(path)
    journal.add_trade(make_trade())
    trade_row = path.read_text(encoding="utf-8").splitlines()[1]
    with path.open("a", encoding="utf-8") as file:
        file.write(trade_row + "\n")

    with pytest.raises(ValueError, match="row 3.*trade-1"):
        CsvTradeJournal(path)


def test_corrupted_row_after_blank_line_reports_physical_line(tmp_path):
    path = tmp_path / "trades.csv"
    path.write_text(
        ",".join(CsvTradeJournal.FIELDNAMES) + "\n\n"
        "trade-1,BTCUSDT,INVALID,100,105,0.01,5,0.1,"
        "2025-01-01T00:00:00,2025-01-02T00:00:00\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="row 3"):
        CsvTradeJournal(path)


def test_existing_empty_file_receives_one_header(tmp_path):
    path = tmp_path / "trades.csv"
    path.touch()

    journal = CsvTradeJournal(path)

    assert journal.trades == ()
    assert path.read_text(encoding="utf-8").splitlines() == [
        ",".join(CsvTradeJournal.FIELDNAMES)
    ]


def test_failed_load_does_not_leave_partial_state(tmp_path):
    path = tmp_path / "trades.csv"
    valid_trade = make_trade()
    journal = CsvTradeJournal(path)
    journal.add_trade(valid_trade)
    with path.open("a", encoding="utf-8") as file:
        file.write("broken,row\n")

    partially_constructed = object.__new__(CsvTradeJournal)

    with pytest.raises(ValueError):
        partially_constructed.__init__(path)

    assert partially_constructed.trades == ()
