"""Optional bank CSV import (#28), isolated from repositories and the core CLI.

Template: date,amount,category with optional note,currency. A signed amount
determines the kind: negative means expense, positive means income. Transfers
must use Ledger.transfer, never a single bank CSV row. Dates and amounts use
TransactionFactory validation. Preview runs the same import against a copy.
"""

from __future__ import annotations

import csv
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from pft.domain.exceptions import DataImportError, FinanceError, InvalidAmountError
from pft.domain.factory import TransactionFactory
from pft.domain.transaction import Transaction
from pft.services.ledger import Ledger

REQUIRED_COLUMNS = frozenset({"date", "amount", "category"})
OPTIONAL_COLUMNS = frozenset({"note", "currency"})
MAX_IMPORT_ROWS = 10_000


@dataclass(frozen=True)
class ImportIssue:
    row_number: int
    reason: str
    field: str | None = None


@dataclass(frozen=True)
class ImportedRow:
    row_number: int
    transaction: Transaction


@dataclass(frozen=True)
class ImportResult:
    accepted: tuple[ImportedRow, ...]
    errors: tuple[ImportIssue, ...]


def _read_rows(source: TextIO) -> list[tuple[int, dict[str, str]] | ImportIssue]:
    """Parse the whole file before mutation; structural CSV errors abort safely.

    Row numbers are physical line numbers at the end of each CSV record, so a
    quoted multi-line note identifies the last line of its record.
    """
    reader = csv.reader(source, strict=True)
    try:
        raw_header = next(reader, None)
        if raw_header is None:
            raise DataImportError("CSV is empty; include date,amount,category headers.")
        header = [value.strip().lower() for value in raw_header]
        if header:
            header[0] = header[0].removeprefix("\ufeff")
        if len(set(header)) != len(header):
            raise DataImportError("CSV contains duplicate column names.")
        missing = REQUIRED_COLUMNS - set(header)
        unknown = set(header) - REQUIRED_COLUMNS - OPTIONAL_COLUMNS
        if missing:
            raise DataImportError("CSV is missing columns: " + ", ".join(sorted(missing)))
        if unknown:
            raise DataImportError("CSV has unsupported columns: " + ", ".join(sorted(unknown)))
        rows: list[tuple[int, dict[str, str]] | ImportIssue] = []
        for values in reader:
            if not values or all(not value.strip() for value in values):
                continue
            if len(rows) >= MAX_IMPORT_ROWS:
                raise DataImportError(f"CSV exceeds the {MAX_IMPORT_ROWS} row limit.")
            if len(values) != len(header):
                rows.append(ImportIssue(reader.line_num, "Row has the wrong number of columns."))
            else:
                rows.append((reader.line_num, dict(zip(header, values, strict=True))))
        return rows
    except csv.Error as exc:
        raise DataImportError(f"Invalid CSV near line {reader.line_num}: {exc}") from exc


class BankCsvImporter:
    """Import valid rows and report rejected ones; the caller owns persistence.

    Use preview before committing. Importing the same file twice intentionally
    imports it twice: this template has no bank-provided unique transaction key.
    """

    def preview(self, ledger: Ledger, source: TextIO, account_id: int) -> ImportResult:
        """Return candidate transactions/errors without changing the caller's Ledger."""
        # Build an observer-free copy: preview must not print/send budget warnings.
        copied = Ledger()
        for account in ledger.accounts:
            copied.restore_account(deepcopy(account))
        copied.restore_id_counters(ledger.next_account_id, ledger.highest_transaction_id + 1)
        return self.import_stream(copied, source, account_id)

    def import_file(self, ledger: Ledger, path: str | Path, account_id: int) -> ImportResult:
        """Read UTF-8 (with or without BOM), preserving CSV embedded newlines."""
        with Path(path).open(encoding="utf-8-sig", newline="") as source:
            return self.import_stream(ledger, source, account_id)

    def import_stream(self, ledger: Ledger, source: TextIO, account_id: int) -> ImportResult:
        account = ledger.account(account_id)
        rows = _read_rows(source)
        accepted: list[ImportedRow] = []
        errors: list[ImportIssue] = []
        for item in rows:
            if isinstance(item, ImportIssue):
                errors.append(item)
                continue
            number, row = item
            amount = row["amount"].strip()
            negative = amount.startswith("-")
            try:
                if re.fullmatch(r"[+-]?\d*(?:[.,]\d*)?", amount) is None:
                    raise InvalidAmountError(
                        "Use one signed decimal amount, like -12.50.", field="amount"
                    )
                transaction = TransactionFactory.from_input(
                    "expense" if negative else "income",
                    amount[1:] if negative else amount,
                    row["category"],
                    row["date"],
                    account_id,
                    row.get("note", ""),
                    transaction_id=ledger.next_transaction_id(),
                    currency=row.get("currency", "").strip() or account.opening_balance.currency,
                )
                ledger.add_transaction(account_id, transaction)
            except FinanceError as exc:
                errors.append(ImportIssue(number, exc.message, exc.field))
            else:
                accepted.append(ImportedRow(number, transaction))
        return ImportResult(tuple(accepted), tuple(errors))
