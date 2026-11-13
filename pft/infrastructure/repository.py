"""Repositories: save and load the whole Ledger, never leaving a half-written file (#18).

``Repository`` is the abstract interface (the Repository pattern): the rest of the program
asks for ``load()`` / ``save(ledger)`` and does not care whether the data sits in CSV files,
one JSON file or SQLite. Three implementations follow:

- ``CsvRepository``: accounts.csv, transactions.csv, budgets.csv and recurring.csv in a folder.
- ``JsonRepository``: the same data in one JSON file.
- ``SqliteRepository``: SQLite, where one database transaction makes a save all-or-nothing.

File repositories write through ``atomic_write``: the new content goes to a temporary file
and replaces the old file only when writing finished, so a crash leaves the old file intact.
CSV spreads one save over several files, so ``CsvRepository`` writes every new file first and
swaps them in together; if any step fails, the complete previous snapshot is put back.
SQLite is the store the API uses because a single transaction covers everything.

The next account and transaction ID are stored with the data (counters.csv, a "counters" JSON
object, an id_counters table), so an ID that belonged to a deleted account or transaction is
never used again, even after a reload.

Recurring rules (#25) are saved with the ledger: recurring.csv, a "recurring" list in JSON,
and a recurring table in SQLite (same database transaction as everything else). Budgets do
not exist yet (#27); budgets.csv is created with only a header and never overwritten.
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any, TextIO

from pft.domain.account import Account
from pft.domain.category import AccountType
from pft.domain.exceptions import DataImportError, FinanceError, StorageError
from pft.domain.factory import TransactionFactory
from pft.domain.money import Money
from pft.domain.recurring import RecurringTransaction
from pft.domain.transaction import CSV_COLUMNS, Transaction
from pft.infrastructure import db
from pft.services.ledger import Ledger

ACCOUNT_COLUMNS: tuple[str, ...] = ("id", "name", "type", "opening_balance", "currency")
BUDGET_COLUMNS: tuple[str, ...] = ("category", "month", "limit", "currency")
RECURRING_COLUMNS: tuple[str, ...] = (
    "account_id",
    "kind",
    "amount",
    "category",
    "note",
    "frequency",
    "start_date",
    "end_date",
    "last_run",
)
COUNTER_COLUMNS: tuple[str, ...] = ("name", "value")
ACCOUNT_COUNTER = "next_account_id"
TRANSACTION_COUNTER = "next_transaction_id"
JSON_VERSION = 1


@contextmanager
def atomic_write(path: Path) -> Iterator[TextIO]:
    """Open ``path`` for writing; the old file is replaced only if the block finishes.

    Anything raised inside the block (or a crash before ``os.replace``) leaves the old file
    exactly as it was and removes the temporary file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", newline="", encoding="utf-8") as f:
            yield f
            f.flush()
            os.fsync(f.fileno())  # data is on disk before the old file is replaced
        os.replace(tmp, path)  # atomic: readers see the old file or the new one, never a mix
    finally:
        if tmp.exists():
            tmp.unlink()  # clean up after a failure


class Repository(ABC):
    """Saves and loads a complete Ledger."""

    @abstractmethod
    def load(self) -> Ledger:
        """Return the stored Ledger; an empty Ledger when nothing was saved yet."""

    @abstractmethod
    def save(self, ledger: Ledger) -> None:
        """Store the whole Ledger. On failure the previously stored data is unchanged."""


# --- shared helpers ---------------------------------------------------------------------


def _sorted_transactions(ledger: Ledger) -> list[Transaction]:
    found = (t for t in ledger.all_transactions() if isinstance(t, Transaction))
    return sorted(found, key=lambda t: t.id)


def _account_rows(ledger: Ledger) -> list[dict[str, str]]:
    return [
        {
            "id": str(a.id),
            "name": a.name,
            "type": a.type.value,
            "opening_balance": str(a.opening_balance.amount),
            "currency": a.opening_balance.currency,
        }
        for a in sorted(ledger.accounts, key=lambda a: a.id)
    ]


def _transaction_rows(ledger: Ledger) -> list[dict[str, str]]:
    return [t.to_row() for t in _sorted_transactions(ledger)]


def _recurring_rows(ledger: Ledger) -> list[dict[str, str]]:
    return [r.to_row() for r in ledger.recurring]


def _counters(ledger: Ledger) -> dict[str, int]:
    return {
        ACCOUNT_COUNTER: ledger.next_account_id,
        TRANSACTION_COUNTER: ledger.highest_transaction_id + 1,
    }


def _account_from_row(row: Mapping[str, Any]) -> Account:
    try:
        return Account(
            int(row["id"]),
            str(row["name"]),
            AccountType.from_text(str(row["type"])),
            Money.of(str(row["opening_balance"]), str(row["currency"])),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise DataImportError(f"bad account row: {exc!r}") from exc


def _text(value: object) -> str | None:
    """Stored values as text; null stays None so the factory reports a missing column."""
    return None if value is None else str(value)


def _build_ledger(
    account_rows: Sequence[Mapping[str, Any]],
    transaction_rows: Sequence[Mapping[str, Any]],
    source: str,
    recurring_rows: Sequence[Mapping[str, Any]] = (),
    counters: Mapping[str, Any] | None = None,
) -> Ledger:
    """Rebuild a Ledger from stored rows; a bad row is reported with its position."""
    ledger = Ledger()
    for number, account_row in enumerate(account_rows, start=1):
        try:
            ledger.restore_account(_account_from_row(account_row))
        except FinanceError as exc:
            raise DataImportError(
                f"{source}, account {number}: {exc.message}", field=exc.field
            ) from exc
    for number, row in enumerate(transaction_rows, start=1):
        try:
            transaction = TransactionFactory.from_row({k: _text(v) for k, v in row.items()})
            ledger.account(transaction.account_id).add(transaction)
        except FinanceError as exc:
            raise DataImportError(
                f"{source}, transaction {number}: {exc.message}", field=exc.field
            ) from exc
    for number, row in enumerate(recurring_rows, start=1):
        try:
            text = {k: "" if v is None else str(v) for k, v in row.items()}
            ledger.add_recurring(RecurringTransaction.from_row(text))
        except FinanceError as exc:
            raise DataImportError(
                f"{source}, recurring rule {number}: {exc.message}", field=exc.field
            ) from exc
    if counters:
        try:
            ledger.restore_id_counters(
                int(counters.get(ACCOUNT_COUNTER, 1)), int(counters.get(TRANSACTION_COUNTER, 1))
            )
        except (TypeError, ValueError) as exc:
            raise DataImportError(f"{source}: bad ID counter: {exc!r}") from exc
    return ledger


# --- CSV ----------------------------------------------------------------------------------


class CsvRepository(Repository):
    """CSV files in one folder (Appendix B). A missing folder or file means no data.

    A save writes every file to ``<name>.tmp`` first. Only when all of them are complete are
    the old files moved to ``<name>.bak`` and the new ones moved into place. If anything fails
    the ``.bak`` files are moved back, so the folder always holds one complete snapshot, never
    a mix of old and new files. If the program dies during the swap itself, the next load or
    save finds the ``.bak`` files and restores that snapshot.
    """

    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def load(self) -> Ledger:
        self._recover()
        accounts = self._read("accounts.csv", ACCOUNT_COLUMNS)
        transactions = self._read("transactions.csv", CSV_COLUMNS)
        recurring = self._read("recurring.csv", RECURRING_COLUMNS)
        counters = {r["name"]: r["value"] for r in self._read("counters.csv", COUNTER_COLUMNS)}
        return _build_ledger(
            list(accounts), list(transactions), str(self.folder), recurring, counters
        )

    def save(self, ledger: Ledger) -> None:
        files: dict[str, tuple[tuple[str, ...], list[dict[str, str]]]] = {
            "accounts.csv": (ACCOUNT_COLUMNS, _account_rows(ledger)),
            "transactions.csv": (CSV_COLUMNS, _transaction_rows(ledger)),
            "recurring.csv": (RECURRING_COLUMNS, _recurring_rows(ledger)),
            "counters.csv": (
                COUNTER_COLUMNS,
                [{"name": k, "value": str(v)} for k, v in _counters(ledger).items()],
            ),
        }
        try:
            self._recover()
            if not (self.folder / "budgets.csv").exists():  # never overwrite #27's data
                files["budgets.csv"] = (BUDGET_COLUMNS, [])
            self._swap_in(files)
        except OSError as exc:
            raise StorageError(f"could not save to {self.folder}: {exc}") from exc

    def _swap_in(self, files: dict[str, tuple[tuple[str, ...], list[dict[str, str]]]]) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        staged: list[Path] = []
        backed_up: list[str] = []
        replaced: list[str] = []
        try:
            for name, (columns, rows) in files.items():  # step 1: write everything new
                tmp = self.folder / f"{name}.tmp"
                staged.append(tmp)
                self._write(tmp, columns, rows)
            for name in files:  # step 2: keep the old snapshot
                if (self.folder / name).exists():
                    os.replace(self.folder / name, self.folder / f"{name}.bak")
                    backed_up.append(name)
            for name in files:  # step 3: put the new snapshot in place
                os.replace(self.folder / f"{name}.tmp", self.folder / name)
                replaced.append(name)
        except BaseException:
            for name in replaced:  # remove what was already moved in, then restore the old files
                (self.folder / name).unlink(missing_ok=True)
            for name in backed_up:
                os.replace(self.folder / f"{name}.bak", self.folder / name)
            raise
        finally:
            for tmp in staged:
                tmp.unlink(missing_ok=True)
        for name in backed_up:  # success: the old snapshot is no longer needed
            (self.folder / f"{name}.bak").unlink(missing_ok=True)

    def _recover(self) -> None:
        """Finish an interrupted swap by restoring the snapshot kept in the .bak files."""
        if not self.folder.exists():
            return
        for bak in sorted(self.folder.glob("*.csv.bak")):
            os.replace(bak, bak.with_suffix(""))
        for tmp in self.folder.glob("*.csv.tmp"):
            tmp.unlink(missing_ok=True)

    def _read(self, name: str, columns: tuple[str, ...]) -> list[dict[str, str]]:
        path = self.folder / name
        if not path.exists():
            return []
        try:
            with path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    return []
                missing = [c for c in columns if c not in reader.fieldnames]
                if missing:
                    raise DataImportError(f"{name} is missing column(s): {', '.join(missing)}")
                return [{k: v for k, v in row.items() if k is not None} for row in reader]
        except OSError as exc:
            raise StorageError(f"could not read {path}: {exc}") from exc

    def _write(self, path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())  # data is on disk before the old file is replaced


# --- JSON ---------------------------------------------------------------------------------


class JsonRepository(Repository):
    """Everything in one JSON file. A missing file means no data."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Ledger:
        document = self._read()
        return _build_ledger(
            list(document.get("accounts", [])),
            list(document.get("transactions", [])),
            str(self.path),
            list(document.get("recurring", [])),
            document["counters"] if isinstance(document.get("counters"), dict) else None,
        )

    def save(self, ledger: Ledger) -> None:
        # Budgets belong to a later task (#27); carry over whatever is stored.
        try:
            previous = self._read()
        except DataImportError:
            previous = {}  # an unreadable old file is replaced by a good one
        document = {
            "version": JSON_VERSION,
            "accounts": _account_rows(ledger),
            "transactions": _transaction_rows(ledger),
            "budgets": previous.get("budgets", []),
            "recurring": _recurring_rows(ledger),
            "counters": _counters(ledger),
        }
        try:
            with atomic_write(self.path) as f:
                json.dump(document, f, indent=2)
                f.write("\n")
        except OSError as exc:
            raise StorageError(f"could not save to {self.path}: {exc}") from exc

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise StorageError(f"could not read {self.path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise DataImportError(f"{self.path} is not valid JSON: {exc}") from exc
        if not isinstance(document, dict):
            raise DataImportError(f"{self.path} must contain a JSON object")
        return document


# --- SQLite -------------------------------------------------------------------------------


def _to_cents(money: Money) -> int:
    """Exact integer cents; an amount with sub-cent digits is refused, never rounded."""
    cents = money.amount.scaleb(2)
    if cents != cents.to_integral_value():
        raise StorageError(f"amount {money.amount} has more than two decimal places")
    return int(cents)


def _from_cents(cents: int) -> str:
    return str(Decimal(cents).scaleb(-2))


class SqliteRepository(Repository):
    """SQLite behind the Repository interface; the path defaults to db.get_db_path().

    ``save`` replaces the stored data inside one database transaction. If anything fails
    (a constraint, a full disk) SQLite rolls back and the previous data is untouched.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path

    def _path(self) -> Path:
        return self.path if self.path is not None else db.get_db_path()

    def load(self) -> Ledger:
        path = self._path()
        if not path.exists():
            return Ledger()
        try:
            db.init_db(path)  # upgrades an older database before reading it
            conn = db.connect(path)
            try:
                accounts = [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "type": r["type"],
                        "opening_balance": _from_cents(r["opening_balance_cents"]),
                        "currency": r["currency"],
                    }
                    for r in conn.execute("SELECT * FROM accounts ORDER BY id")
                ]
                transactions = [
                    {
                        "id": r["id"],
                        "account_id": r["account_id"],
                        "kind": r["kind"],
                        "amount": _from_cents(r["amount_cents"]),
                        "currency": r["currency"],
                        "date": r["occurred_on"],
                        "category": r["category"],
                        "note": r["note"],
                        "transfer_id": r["transfer_id"] or "",
                        "direction": r["direction"] or "",
                    }
                    for r in conn.execute("SELECT * FROM transactions ORDER BY id")
                ]
                recurring = [
                    {
                        "account_id": r["account_id"],
                        "kind": r["kind"],
                        "amount": _from_cents(r["amount_cents"]),
                        "category": r["category"],
                        "note": r["note"],
                        "frequency": r["frequency"],
                        "start_date": r["start_date"],
                        "end_date": r["end_date"] or "",
                        "last_run": r["last_run"] or "",
                    }
                    for r in conn.execute("SELECT * FROM recurring ORDER BY id")
                ]
                counters = {
                    r["name"]: r["value"] for r in conn.execute("SELECT * FROM id_counters")
                }
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise StorageError(f"could not read {path}: {exc}") from exc
        return _build_ledger(accounts, transactions, str(path), recurring, counters)

    def save(self, ledger: Ledger) -> None:
        path = self._path()
        account_params = [
            (a.id, a.name, a.type.value, _to_cents(a.opening_balance), a.opening_balance.currency)
            for a in ledger.accounts
        ]
        transaction_params = []
        for t in _sorted_transactions(ledger):
            row = t.to_row()
            transaction_params.append(
                (
                    t.id,
                    t.account_id,
                    t.kind.value,
                    _to_cents(t.amount),
                    t.amount.currency,
                    t.date.isoformat(),
                    t.category.value,
                    t.note,
                    row["transfer_id"] or None,
                    row["direction"] or None,
                )
            )
        recurring_params = [
            (
                r.template.account_id,
                r.template.kind.value,
                _to_cents(r.template.amount),
                r.template.category.value,
                r.template.note,
                r.frequency.value,
                r.start.isoformat(),
                r.end.isoformat() if r.end else None,
                r.last_run.isoformat() if r.last_run else None,
            )
            for r in ledger.recurring
        ]
        try:
            db.init_db(path)
            conn = db.connect(path)
            try:
                with conn:  # one transaction: commit on success, roll back on any error
                    conn.execute("DELETE FROM recurring")
                    conn.execute("DELETE FROM transactions")
                    conn.execute("DELETE FROM accounts")
                    conn.execute("DELETE FROM id_counters")
                    conn.executemany(
                        "INSERT INTO id_counters (name, value) VALUES (?, ?)",
                        list(_counters(ledger).items()),
                    )
                    conn.executemany(
                        "INSERT INTO accounts (id, name, type, opening_balance_cents, currency) "
                        "VALUES (?, ?, ?, ?, ?)",
                        account_params,
                    )
                    conn.executemany(
                        "INSERT INTO transactions (id, account_id, kind, amount_cents, currency, "
                        "occurred_on, category, note, transfer_id, direction) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        transaction_params,
                    )
                    conn.executemany(
                        "INSERT INTO recurring (account_id, kind, amount_cents, category, note, "
                        "frequency, start_date, end_date, last_run) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        recurring_params,
                    )
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise StorageError(f"could not save to {path}: {exc}") from exc


__all__ = [
    "CsvRepository",
    "JsonRepository",
    "Repository",
    "SqliteRepository",
    "atomic_write",
]
