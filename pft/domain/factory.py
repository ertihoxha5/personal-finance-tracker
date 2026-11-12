"""TransactionFactory: the one place that turns text into a Transaction (#17, FR-02, FR-03).

Callers never name Income, Expense or Transfer. They hand the factory text and
get back the right subclass:

- ``from_input`` reads what a user typed (CLI arguments, form values).
- ``from_row`` reads a stored CSV row, the exact mapping ``to_row()`` wrote, so
  ``from_row(t.to_row()) == t`` for every kind.

The class is chosen by dictionary dispatch on ``Kind`` (``_CLASSES``), not by an
if/elif chain, and Transfer's two extra fields come from a per-kind
``_ROW_EXTRAS`` mapping. Adding a kind means adding one entry to each mapping;
a unit test checks the keys cover every ``Kind``.

Rules agreed for this task:

- ``from_input`` builds income and expense only. A transfer is always a linked
  OUT/IN pair with a shared ``transfer_id``, which is ``Ledger.transfer``'s job,
  so ``kind="transfer"`` raises InvalidTransferError.
- A decimal comma (``12,50``) is accepted in user text only. Stored rows use the
  machine format ``12.50`` that ``to_row`` writes. Text with a comma and a dot
  (``1.234,50``, ``1,234.50``), more than one comma, or more than two decimals
  is rejected as ambiguous, matching React's ``parseMoneyInput``.
- Dates must be exactly ``YYYY-MM-DD``. Since Python 3.11 ``date.fromisoformat``
  also accepts ``20261117`` and week dates such as ``2026-W47-2``, so the shape
  is checked with a pattern first; one format is stored everywhere.
- Errors: a bad amount raises InvalidAmountError, a bad date InvalidDateError,
  an unknown category InvalidCategoryError. Problems with a row's structure
  (missing column, unknown kind or direction, non-integer id, transfer columns
  on a non-transfer row) raise DataImportError, so the repository (#18) can
  catch it and add the row number.
- IDs are never invented here (see pft/domain/transaction.py): ``from_input``
  takes the ID its caller assigns, and ``from_row`` restores the stored one.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable, Mapping
from typing import Any, ClassVar

from pft.domain.category import Category, Direction, Kind
from pft.domain.exceptions import (
    DataImportError,
    InvalidAmountError,
    InvalidChoiceError,
    InvalidDateError,
    InvalidTransferError,
)
from pft.domain.money import DEFAULT_CURRENCY, Money
from pft.domain.transaction import CSV_COLUMNS, Expense, Income, Transaction, Transfer

# A plain decimal number with an optional sign: "12", "-3", "12.5", ".5", "12.".
# The sign is allowed here so "-5" gets the clearer "must be positive" message later.
_USER_AMOUNT = re.compile(r"[+-]?\d*(?:\.(?P<decimals>\d*))?")
# date.fromisoformat also takes "20261117" and week dates like "2026-W47-2" (10 characters),
# so the exact shape is checked first.
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TRANSFER_COLUMNS: tuple[str, ...] = ("transfer_id", "direction")


def _parse_amount(text: object, currency: str = DEFAULT_CURRENCY) -> Money:
    """Parse a user-typed amount such as ' 12,50 ' into Money.

    One comma and no dot is a decimal comma. Any other use of a comma is a
    thousands separator or a typo and is rejected. Signs are left to the
    PositiveAmount check on the transaction, which rejects zero and negatives.
    """
    if not isinstance(text, str):
        raise InvalidAmountError(f"amount must be text, got {type(text).__name__}", field="amount")
    cleaned = text.strip()
    if "," in cleaned:
        if cleaned.count(",") > 1 or "." in cleaned:
            raise InvalidAmountError(
                f"ambiguous amount {text!r}; write it like 1234.50 without thousands separators",
                field="amount",
            )
        cleaned = cleaned.replace(",", ".")
    match = _USER_AMOUNT.fullmatch(cleaned)
    if match is None or not any(ch.isdigit() for ch in cleaned):
        raise InvalidAmountError(
            f"invalid amount {text!r}; enter a number like 12.50", field="amount"
        )
    if len(match["decimals"] or "") > 2:
        raise InvalidAmountError(
            f"amount {text!r} has more than two decimal places", field="amount"
        )
    return Money.of(cleaned, currency)


def _parse_date(text: object) -> dt.date:
    """Parse an ISO date 'YYYY-MM-DD' (exactly 10 characters, surrounding spaces ignored)."""
    cleaned = text.strip() if isinstance(text, str) else ""
    if _ISO_DATE.fullmatch(cleaned):
        try:
            return dt.date.fromisoformat(cleaned)
        except ValueError:
            pass
    raise InvalidDateError(f"invalid date {text!r}; use the form 2026-11-17", field="date")


def _row_int(row: Mapping[str, str], column: str) -> int:
    """Read an integer column such as 'id' from a row; a bad value is a DataImportError."""
    text = row[column].strip()
    if not re.fullmatch(r"-?\d+", text):
        raise DataImportError(
            f"column {column!r} must be a whole number, got {text!r}", field=column
        )
    return int(text)


def _no_transfer_extras(kind: Kind, row: Mapping[str, str]) -> dict[str, Any]:
    """Extras for income and expense: none, and the transfer columns must be empty."""
    filled = [column for column in _TRANSFER_COLUMNS if row[column].strip()]
    if filled:
        raise DataImportError(
            f"a {kind.value} row must leave {', '.join(filled)} empty", field=filled[0]
        )
    return {}


def _transfer_extras(kind: Kind, row: Mapping[str, str]) -> dict[str, Any]:
    """Extras for a transfer: its direction and the transfer_id shared with its pair."""
    try:
        direction = Direction.from_text(row["direction"])
    except InvalidChoiceError as exc:
        raise DataImportError(exc.message, field="direction") from exc
    return {"direction": direction, "transfer_id": row["transfer_id"]}


class TransactionFactory:
    """Build the right Transaction subclass from user text or a stored CSV row.

    Every method is a class method; the class is never instantiated. Example::

        t = TransactionFactory.from_input("expense", "12,50", "food", "2026-11-17", 1,
                                          transaction_id=7)
        TransactionFactory.from_row(t.to_row()) == t   # True
    """

    # Dictionary dispatch: which class builds each kind.
    _CLASSES: ClassVar[dict[Kind, type[Transaction]]] = {
        Kind.INCOME: Income,
        Kind.EXPENSE: Expense,
        Kind.TRANSFER: Transfer,
    }

    # The keyword arguments a kind needs beyond the common ones, read from a row.
    _ROW_EXTRAS: ClassVar[dict[Kind, Callable[[Kind, Mapping[str, str]], dict[str, Any]]]] = {
        Kind.INCOME: _no_transfer_extras,
        Kind.EXPENSE: _no_transfer_extras,
        Kind.TRANSFER: _transfer_extras,
    }

    # Kinds from_input may build; a transfer needs Ledger.transfer to create its pair.
    _INPUT_KINDS: ClassVar[frozenset[Kind]] = frozenset({Kind.INCOME, Kind.EXPENSE})

    @classmethod
    def from_input(
        cls,
        kind: str,
        amount: str,
        category: str,
        date: str,
        account_id: int,
        note: str = "",
        *,
        transaction_id: int,
        currency: str = DEFAULT_CURRENCY,
    ) -> Transaction:
        """Build an Income or Expense from user text.

        ``kind`` and ``category`` ignore case and spaces; ``amount`` accepts a
        decimal comma (``12,50``); ``date`` must be ``YYYY-MM-DD``. The caller
        (Ledger or the repository) assigns ``transaction_id``.

        Raises InvalidChoiceError (unknown kind), InvalidTransferError (kind
        transfer), InvalidAmountError, InvalidCategoryError or InvalidDateError.
        """
        parsed_kind = Kind.from_text(kind)
        if parsed_kind not in cls._INPUT_KINDS:
            raise InvalidTransferError(
                "a transfer is a linked pair of transactions; create it with Ledger.transfer",
                field="kind",
            )
        return cls._CLASSES[parsed_kind](
            id=transaction_id,
            account_id=account_id,
            amount=_parse_amount(amount, currency),
            date=_parse_date(date),
            category=Category.from_text(category),
            note=note,
        )

    @classmethod
    def from_row(cls, row: Mapping[str, str | None]) -> Transaction:
        """Rebuild a transaction from a CSV row keyed by CSV_COLUMNS, as to_row() wrote it.

        The stored id and currency are kept, and a transfer gets back its
        direction and transfer_id, so ``from_row(t.to_row()) == t``. Extra
        columns are ignored. ``None`` values (csv.DictReader's filler for a
        short line) count as missing.

        Raises DataImportError for a structural problem, and InvalidAmountError,
        InvalidCurrencyError, InvalidDateError or InvalidCategoryError for a bad value.
        """
        missing = [column for column in CSV_COLUMNS if row.get(column) is None]
        if missing:
            raise DataImportError(
                f"row is missing column(s): {', '.join(missing)}", field=missing[0]
            )
        # Every column is present and a str from here on.
        values: dict[str, str] = {column: str(row[column]) for column in CSV_COLUMNS}

        try:
            kind = Kind.from_text(values["kind"])
        except InvalidChoiceError as exc:
            raise DataImportError(exc.message, field="kind") from exc

        amount_text = values["amount"].strip()
        try:
            amount = Money.of(amount_text, values["currency"].strip())
        except InvalidAmountError as exc:
            raise InvalidAmountError(
                f"invalid amount {amount_text!r} in row", field="amount"
            ) from exc

        return cls._CLASSES[kind](
            id=_row_int(values, "id"),
            account_id=_row_int(values, "account_id"),
            amount=amount,
            date=_parse_date(values["date"]),
            category=Category.from_text(values["category"]),
            note=values["note"],
            **cls._ROW_EXTRAS[kind](kind, values),
        )


__all__ = ["TransactionFactory"]
