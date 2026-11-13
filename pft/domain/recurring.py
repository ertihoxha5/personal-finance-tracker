"""Recurring transactions: rent, salary and subscriptions created automatically (#25, FR-18).

A ``RecurringTransaction`` is a rule: a template Income or Expense, a ``Frequency``, a
start date, an optional end date and ``last_run``, the date of the last occurrence that
was already applied.

Date rule: occurrence *n* is computed from the **start date** and *n*, never from the
previous occurrence. ``Frequency.next_date`` clamps 31 Jan to 28 Feb, and chaining it would
then give 28 Mar (see ``test_chained_monthly_dates_drift_after_a_short_month``). Counting from
the start gives 31 Jan, 28 Feb, 31 Mar, 30 Apr, ... The clamp itself is the same as in
``Frequency.next_date`` (#10): ``occurrence_date(f, start, 1) == f.next_date(start)``.

Duplicates: ``apply_due`` only adds occurrences after ``last_run``, and also skips one that
is already in the account (same kind, amount, date, category and note), so running it twice,
or again after a restart that lost ``last_run``, adds nothing new.

This module imports nothing from services: ``apply_due`` takes anything shaped like the
Ledger (``LedgerLike``), so the domain does not depend on the layer above it.
"""

from __future__ import annotations

import calendar
import datetime as dt
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from itertools import count
from typing import Protocol

from pft.domain.category import Frequency
from pft.domain.exceptions import (
    DataImportError,
    InvalidChoiceError,
    InvalidDateError,
    InvalidTransferError,
)
from pft.domain.factory import TransactionFactory
from pft.domain.transaction import Transaction, Transfer

# Error fields use the stored column names (RECURRING_COLUMNS), which the API also uses.
_FIELDS = {"start": "start_date", "end": "end_date", "last_run": "last_run"}


def _clamped(year: int, month: int, day: int) -> dt.date:
    """The date, with the day moved to the month's last day if the month is shorter."""
    return dt.date(year, month, min(day, calendar.monthrange(year, month)[1]))


def occurrence_date(frequency: Frequency, start: dt.date, index: int) -> dt.date:
    """Date of occurrence ``index`` (0 = start), counted from ``start``, not from the last one.

    >>> occurrence_date(Frequency.MONTHLY, dt.date(2027, 1, 31), 2)
    datetime.date(2027, 3, 31)
    """
    if index < 0:
        raise ValueError("index must be 0 or more")
    if frequency is Frequency.WEEKLY:
        return start + dt.timedelta(weeks=index)
    if frequency is Frequency.MONTHLY:
        months = start.month - 1 + index
        return _clamped(start.year + months // 12, months % 12 + 1, start.day)
    return _clamped(start.year + index, start.month, start.day)


class LedgerLike(Protocol):
    """What apply_due needs from the Ledger (pft.services.ledger.Ledger fits)."""

    def account(self, account_id: int) -> Iterable[object]: ...

    def add_transaction(self, account_id: int, transaction: Transaction) -> None: ...

    def next_transaction_id(self) -> int: ...


def _same_item(a: object, b: Transaction) -> bool:
    """True when ``a`` is the same money movement as ``b``, ignoring the ID."""
    if not isinstance(a, Transaction):
        return False
    row_a, row_b = a.to_row(), b.to_row()
    del row_a["id"], row_b["id"]
    return row_a == row_b


@dataclass(kw_only=True)
class RecurringTransaction:
    """A rule that creates a copy of ``template`` on every due date.

    ``template`` is an Income or Expense; its own date and ID are ignored. ``end`` is
    inclusive. ``last_run`` is the date of the last occurrence already applied (None
    before the first run); saving it with the rule keeps a restart from adding duplicates.
    """

    template: Transaction
    frequency: Frequency
    start: dt.date
    end: dt.date | None = None
    last_run: dt.date | None = None

    def __post_init__(self) -> None:
        if isinstance(self.template, Transfer):
            raise InvalidTransferError("recurring transfers are not supported", field="kind")
        if not isinstance(self.template, Transaction):
            raise InvalidChoiceError("template must be an income or expense", field="kind")
        if not isinstance(self.frequency, Frequency):
            raise InvalidChoiceError(
                f"frequency must be a Frequency, got {self.frequency!r}", field="frequency"
            )
        for name in ("start", "end", "last_run"):
            value = getattr(self, name)
            if value is None and name != "start":
                continue
            if not isinstance(value, dt.date) or isinstance(value, dt.datetime):
                raise InvalidDateError(
                    f"{name} must be a date such as 2026-09-01", field=_FIELDS[name]
                )
        if self.end is not None and self.end < self.start:
            raise InvalidDateError("end date must be on or after the start date", field="end_date")

    def dates(self, until: dt.date) -> Iterator[dt.date]:
        """Yield each due date after ``last_run`` up to ``until`` and ``end`` (both inclusive).

        A generator: dates are computed one at a time, only when the caller asks for the
        next one, so ``dates(date.max)`` on a rule without an end is safe with ``islice``.
        """
        limit = until if self.end is None else min(until, self.end)
        for index in count():
            day = occurrence_date(self.frequency, self.start, index)
            if day > limit:
                return
            if self.last_run is None or day > self.last_run:
                yield day

    def occurrences(self, until: dt.date, *, first_id: int) -> Iterator[Transaction]:
        """Yield a copy of the template for each due date, with IDs first_id, first_id + 1, ..."""
        for tx_id, day in zip(count(first_id), self.dates(until), strict=False):
            yield self.template.copy_for(day, new_id=tx_id)

    def apply_due(self, ledger: LedgerLike, today: dt.date) -> list[Transaction]:
        """Add every occurrence due by ``today`` that is missing, then move ``last_run``.

        Returns the transactions that were added. Calling it again with the same
        ``today`` adds nothing.
        """
        account_id = self.template.account_id
        existing = list(ledger.account(account_id))
        added: list[Transaction] = []
        for item in self.occurrences(today, first_id=ledger.next_transaction_id()):
            if not any(_same_item(old, item) for old in existing):
                ledger.add_transaction(account_id, item)
                added.append(item)
            self.last_run = item.date
        return added

    def upcoming(self, after: dt.date, limit: int) -> list[dt.date]:
        """The next ``limit`` dates strictly after ``after`` (for previews; ignores last_run)."""
        result: list[dt.date] = []
        end = self.end or dt.date.max
        for index in count():
            if len(result) == limit:
                break
            try:
                day = occurrence_date(self.frequency, self.start, index)
            except (ValueError, OverflowError):  # past year 9999
                break
            if day > end:
                break
            if day > after:
                result.append(day)
        return result

    # --- storage: the RECURRING_COLUMNS of pft.infrastructure.repository ----------------

    def to_row(self) -> dict[str, str]:
        """The rule as text, keyed like RECURRING_COLUMNS; last_run is saved with it."""
        t = self.template
        return {
            "account_id": str(t.account_id),
            "kind": t.kind.value,
            "amount": str(t.amount.amount),
            "category": t.category.value,
            "note": t.note,
            "frequency": self.frequency.value,
            "start_date": self.start.isoformat(),
            "end_date": self.end.isoformat() if self.end else "",
            "last_run": self.last_run.isoformat() if self.last_run else "",
        }

    @classmethod
    def from_row(cls, row: Mapping[str, str]) -> RecurringTransaction:
        """Rebuild a rule saved by to_row(), so ``from_row(r.to_row()) == r``."""
        try:
            start = row["start_date"]
            template = TransactionFactory.from_input(
                row["kind"],
                row["amount"],
                row["category"],
                start,
                int(row["account_id"]),
                row["note"],
                transaction_id=0,
            )
            return cls(
                template=template,
                frequency=Frequency.from_text(row["frequency"]),
                start=template.date,
                end=_optional_date(row["end_date"], "end_date"),
                last_run=_optional_date(row["last_run"], "last_run"),
            )
        except KeyError as exc:
            raise DataImportError(f"recurring row is missing column {exc}", field=str(exc)) from exc
        except ValueError as exc:
            raise DataImportError(f"invalid recurring row: {exc}", field="account_id") from exc


def _optional_date(text: str, field: str) -> dt.date | None:
    text = text.strip()
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text)
    except ValueError as exc:
        raise InvalidDateError(f"invalid date {text!r}; use 2026-09-01", field=field) from exc


__all__ = ["LedgerLike", "RecurringTransaction", "occurrence_date"]
