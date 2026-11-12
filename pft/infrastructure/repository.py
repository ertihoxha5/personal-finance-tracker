"""Repositories: save and load the whole Ledger, never leaving a half-written file (#18).

``Repository`` is the abstract interface (the Repository pattern): the rest of the program
asks for ``load()`` / ``save(ledger)`` and does not care whether the data sits in CSV files,
one JSON file or SQLite. Three implementations follow:

- ``CsvRepository``: accounts.csv, transactions.csv, budgets.csv and recurring.csv in a folder.
- ``JsonRepository``: the same data in one JSON file.
- ``SqliteRepository``: SQLite, where one database transaction makes a save all-or-nothing.

File repositories write through ``atomic_write``: the new content goes to a temporary file
and replaces the old file only when writing finished, so a crash leaves the old file intact.
CSV spreads one save over several files, so each file is atomic on its own; SQLite is the
store the API uses because a single transaction covers everything.

Budgets and recurring rules do not exist yet (#25, #27). Their files are created with only a
header and are never overwritten, so data written by those tasks later is not lost.
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
    return ledger


# --- CSV ----------------------------------------------------------------------------------


class CsvRepository(Repository):
    """Four CSV files in one folder (Appendix B). A missing folder or file means no data."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def load(self) -> Ledger:
        accounts = self._read("accounts.csv", ACCOUNT_COLUMNS)
        transactions = self._read("transactions.csv", CSV_COLUMNS)
        return _build_ledger(list(accounts), list(transactions), str(self.folder))

    def save(self, ledger: Ledger) -> None:
        try:
            self._write("accounts.csv", ACCOUNT_COLUMNS, _account_rows(ledger))
            self._write("transactions.csv", CSV_COLUMNS, _transaction_rows(ledger))
            for name, columns in (
                ("budgets.csv", BUDGET_COLUMNS),
                ("recurring.csv", RECURRING_COLUMNS),
            ):
                if not (self.folder / name).exists():  # never overwrite another task's data
                    self._write(name, columns, [])
        except OSError as exc:
            raise StorageError(f"could not save to {self.folder}: {exc}") from exc

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

    def _write(self, name: str, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
        with atomic_write(self.folder / name) as f:
            writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)


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
        )

    def save(self, ledger: Ledger) -> None:
        # Budgets and recurring rules belong to later tasks; carry over whatever is stored.
        try:
            previous = self._read()
        except DataImportError:
            previous = {}  # an unreadable old file is replaced by a good one
        document = {
            "version": JSON_VERSION,
            "accounts": _account_rows(ledger),
            "transactions": _transaction_rows(ledger),
            "budgets": previous.get("budgets", []),
            "recurring": previous.get("recurring", []),
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
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise StorageError(f"could not read {path}: {exc}") from exc
        return _build_ledger(accounts, transactions, str(path))

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
        try:
            db.init_db(path)
            conn = db.connect(path)
            try:
                with conn:  # one transaction: commit on success, roll back on any error
                    conn.execute("DELETE FROM transactions")
                    conn.execute("DELETE FROM accounts")
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
