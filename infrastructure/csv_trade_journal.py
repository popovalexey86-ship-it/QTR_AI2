import csv
from datetime import datetime
import os
from pathlib import Path

from core.decision import Decision
from core.trade import Trade
from core.trade_journal import TradeJournalWriteError


class CsvTradeJournal:
    """Persistent CSV implementation of the trade journal port."""

    FIELDNAMES = (
        "ticket",
        "symbol",
        "decision",
        "entry",
        "exit",
        "volume",
        "pnl",
        "fees",
        "opened_at",
        "closed_at",
    )

    def __init__(self, path: Path) -> None:
        self._path = path
        self._trades: list[Trade] = []
        self._tickets: set[str] = set()

        self._path.parent.mkdir(parents=True, exist_ok=True)

        if not self._path.exists() or self._path.stat().st_size == 0:
            self._write_header()
        else:
            self._load_trades()

    def add_trade(self, trade: Trade) -> bool:
        if trade.ticket in self._tickets:
            return False

        row = self._to_row(trade)

        try:
            with self._path.open("a", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=self.FIELDNAMES)
                writer.writerow(row)
                file.flush()
                os.fsync(file.fileno())
        except (OSError, csv.Error) as error:
            raise TradeJournalWriteError(
                f"Failed to write trade journal '{self._path}' "
                f"for ticket '{trade.ticket}'."
            ) from error

        self._trades.append(trade)
        self._tickets.add(trade.ticket)
        return True

    @property
    def trades(self) -> tuple[Trade, ...]:
        return tuple(self._trades)

    def _write_header(self) -> None:
        with self._path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=self.FIELDNAMES)
            writer.writeheader()

    def _load_trades(self) -> None:
        loaded_trades: list[Trade] = []
        loaded_tickets: set[str] = set()

        with self._path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)

            if tuple(reader.fieldnames or ()) != self.FIELDNAMES:
                raise ValueError("Incompatible trade journal CSV header.")

            for row in reader:
                line_number = reader.line_num
                try:
                    trade = self._from_row(row)
                except (KeyError, TypeError, ValueError) as error:
                    raise ValueError(
                        f"Invalid trade journal CSV row {line_number}: {error}"
                    ) from error

                if trade.ticket in loaded_tickets:
                    raise ValueError(
                        f"Duplicate ticket in trade journal CSV row {line_number}: "
                        f"{trade.ticket}"
                    )

                loaded_trades.append(trade)
                loaded_tickets.add(trade.ticket)

        self._trades = loaded_trades
        self._tickets = loaded_tickets

    @classmethod
    def _to_row(cls, trade: Trade) -> dict[str, str]:
        return {
            "ticket": trade.ticket,
            "symbol": trade.symbol,
            "decision": trade.decision.value,
            "entry": str(trade.entry),
            "exit": str(trade.exit),
            "volume": str(trade.volume),
            "pnl": str(trade.pnl),
            "fees": str(trade.fees),
            "opened_at": trade.opened_at.isoformat(),
            "closed_at": trade.closed_at.isoformat(),
        }

    @classmethod
    def _from_row(cls, row: dict[str, str | None]) -> Trade:
        if set(row) != set(cls.FIELDNAMES) or any(
            row[field] is None for field in cls.FIELDNAMES
        ):
            raise ValueError("Unexpected CSV columns.")

        return Trade(
            ticket=row["ticket"] or "",
            symbol=row["symbol"] or "",
            decision=Decision(row["decision"] or ""),
            entry=float(row["entry"] or ""),
            exit=float(row["exit"] or ""),
            volume=float(row["volume"] or ""),
            pnl=float(row["pnl"] or ""),
            fees=float(row["fees"] or ""),
            opened_at=datetime.fromisoformat(row["opened_at"] or ""),
            closed_at=datetime.fromisoformat(row["closed_at"] or ""),
        )
