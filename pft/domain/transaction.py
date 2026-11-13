"""Transaction hierarchy: Income, Expense and Transfer (#14, FR-02, FR-03).

``Transaction`` is an abstract dataclass. It holds what every transaction has
and declares ``signed_amount()`` and ``kind`` as abstract, so
``Transaction(...)`` raises TypeError and only the three concrete kinds can be
created. Code that totals or lists transactions calls ``t.signed_amount()``
without checking the type: each subclass knows its own sign (polymorphism).

Data rules (Appendix B):

- ``amount`` is always positive Money, checked by the #12 ``PositiveAmount``
  descriptor on every assignment. The kind (and a transfer's direction) gives
  the sign.
- Dates are ``datetime.date``; a ``datetime`` is rejected because comparing the
  two raises TypeError while sorting.
- IDs are ints, like Account and Ledger. The caller (Ledger or the repository)
  assigns them; this class never invents one.

Every class is ``@dataclass(kw_only=True)``: calls must name each argument,
and Transfer can add required fields after the base class's defaulted ones.
The classes are not frozen and have no slots (the #12 descriptor rules).

Equality compares every field, including ``id``; because the classes are
mutable dataclasses with ``__eq__``, they are unhashable. Key dictionaries
and sets by ``t.id``. Ordering (``<``, used by ``sorted``) compares dates only.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Self

from pft.domain.category import Category, Direction, Kind
from pft.domain.exceptions import (
    InvalidCategoryError,
    InvalidChoiceError,
    InvalidDateError,
    InvalidTextError,
    InvalidTransferError,
)
from pft.domain.money import Money
from pft.domain.validators import NonEmptyText, PositiveAmount

# Column names and order for CSV export/import (#17, #21) and the repository (#18).
# to_row() returns exactly these keys, in this order.
CSV_COLUMNS: tuple[str, ...] = (
    "id",
    "account_id",
    "kind",
    "amount",
    "currency",
    "date",
    "category",
    "note",
    "transfer_id",
    "direction",
)


@dataclass(kw_only=True)
class Transaction(ABC):
    """One money movement in one account. Abstract: use Income, Expense or Transfer."""

    id: int
    account_id: int
    amount: PositiveAmount = PositiveAmount()
    date: dt.date
    category: Category
    note: str = ""

    def __post_init__(self) -> None:
        # datetime is a subclass of date, so it must be rejected explicitly.
        if not isinstance(self.date, dt.date) or isinstance(self.date, dt.datetime):
            raise InvalidDateError(
                f"date must be a date such as 2026-11-15, got {type(self.date).__name__}",
                field="date",
            )
        if not isinstance(self.category, Category):
            raise InvalidCategoryError(
                f"category must be a Category, got {self.category!r}", field="category"
            )
        if not isinstance(self.note, str):
            raise InvalidTextError(
                f"note must be text, got {type(self.note).__name__}", field="note"
            )
        self.note = self.note.strip()

    @property
    @abstractmethod
    def kind(self) -> Kind:
        """Which kind of transaction this is."""

    @abstractmethod
    def signed_amount(self) -> Money:
        """The amount with its effect on the account balance: + adds, − subtracts."""

    def to_row(self) -> dict[str, str]:
        """Return the CSV row: every column in CSV_COLUMNS, all values as text."""
        return {
            "id": str(self.id),
            "account_id": str(self.account_id),
            "kind": self.kind.value,
            "amount": str(self.amount.amount),
            "currency": self.amount.currency,
            "date": self.date.isoformat(),
            "category": self.category.value,
            "note": self.note,
            "transfer_id": "",
            "direction": "",
        }

    def __lt__(self, other: object) -> bool:
        """Order by date only, so sorted() lists transactions chronologically.

        sorted() is stable, so transactions on the same date keep their order.
        """
        if not isinstance(other, Transaction):
            return NotImplemented
        return self.date < other.date

    def copy_for(self, new_date: dt.date, *, new_id: int) -> Self:
        """Return a copy dated new_date with a new ID, for a recurring item (#22).

        The original is unchanged. The copy is built through __init__, so every
        field is validated again.
        """
        return dataclasses.replace(self, date=new_date, id=new_id)


@dataclass(kw_only=True)
class Income(Transaction):
    """Money coming into the account, such as a salary."""

    @property
    def kind(self) -> Kind:
        return Kind.INCOME

    def signed_amount(self) -> Money:
        return self.amount


@dataclass(kw_only=True)
class Expense(Transaction):
    """Money leaving the account, such as rent or groceries."""

    @property
    def kind(self) -> Kind:
        return Kind.EXPENSE

    def signed_amount(self) -> Money:
        return -self.amount


@dataclass(kw_only=True)
class Transfer(Transaction):
    """One side of a move between two of the user's own accounts.

    A transfer is stored as two Transfer objects, OUT from one account and IN to
    the other, sharing one ``transfer_id``. Creating the pair is Ledger.transfer's
    job (#23); this class is one side. Its category defaults to OTHER; reports
    leave transfers out by kind, not by category.
    """

    category: Category = Category.OTHER
    direction: Direction
    transfer_id: NonEmptyText = NonEmptyText()

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.direction, Direction):
            raise InvalidChoiceError(
                f"direction must be 'out' or 'in', got {self.direction!r}", field="direction"
            )

    @property
    def kind(self) -> Kind:
        return Kind.TRANSFER

    def signed_amount(self) -> Money:
        return -self.amount if self.direction is Direction.OUT else self.amount

    def to_row(self) -> dict[str, str]:
        row = super().to_row()
        row["transfer_id"] = self.transfer_id
        row["direction"] = self.direction.value
        return row

    def copy_for(self, new_date: dt.date, *, new_id: int) -> Self:
        """Not supported: the copy would share this transfer_id and link unrelated pairs."""
        raise InvalidTransferError("recurring transfers are not supported")


__all__ = ["CSV_COLUMNS", "Expense", "Income", "Transaction", "Transfer"]
