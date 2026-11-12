"""Domain enums: the fixed lists of allowed values.

Every enum is a StrEnum with lowercase values, so a member *is* its string
(``Category.FOOD == "food"``) and serialises unchanged to JSON, CSV and SQLite.
React's label maps (frontend/src/lib/labels.js) are keyed by these values, so
renaming a value is an API change.

``from_text`` is an alternative constructor for user input: it ignores
surrounding whitespace and case, and an unknown value raises an error whose
message lists every valid value.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from enum import StrEnum
from typing import TypeVar

from pft.domain.exceptions import FinanceError, InvalidCategoryError, InvalidChoiceError

_E = TypeVar("_E", bound=StrEnum)


def _parse(
    enum_cls: type[_E],
    text: object,
    *,
    label: str,
    field: str,
    error: type[FinanceError] = InvalidChoiceError,
) -> _E:
    """Return the member of enum_cls whose value matches text, ignoring case and spaces."""
    cleaned = text.strip().lower() if isinstance(text, str) else None
    for member in enum_cls:
        if member.value == cleaned:
            return member
    valid = ", ".join(member.value for member in enum_cls)
    raise error(f"unknown {label} {text!r}; choose one of: {valid}", field=field)


class Category(StrEnum):
    SALARY = "salary"
    FOOD = "food"
    RENT = "rent"
    BILLS = "bills"
    TRANSPORT = "transport"
    FUN = "fun"
    HEALTH = "health"
    EDUCATION = "education"
    OTHER = "other"

    @classmethod
    def from_text(cls, text: str) -> Category:
        """Parse a category name such as ' Food '; raises InvalidCategoryError."""
        return _parse(cls, text, label="category", field="category", error=InvalidCategoryError)


class Kind(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"

    @classmethod
    def from_text(cls, text: str) -> Kind:
        """Parse a transaction kind such as 'Expense'; raises InvalidChoiceError."""
        return _parse(cls, text, label="kind", field="kind")


class AccountType(StrEnum):
    CASH = "cash"
    BANK = "bank"
    CARD = "card"
    SAVINGS = "savings"

    @classmethod
    def from_text(cls, text: str) -> AccountType:
        """Parse an account type such as 'BANK'; raises InvalidChoiceError."""
        return _parse(cls, text, label="account type", field="type")


def add_month(d: date) -> date:
    """Return the same day one month later, clamped to that month's last day."""
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    day = min(d.day, calendar.monthrange(y, m)[1])  # 31 Jan -> 28/29 Feb
    return date(y, m, day)


def add_year(d: date) -> date:
    """Return the same day one year later; 29 Feb becomes 28 Feb in a non-leap year."""
    day = min(d.day, calendar.monthrange(d.year + 1, d.month)[1])
    return date(d.year + 1, d.month, day)


class Frequency(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

    @classmethod
    def from_text(cls, text: str) -> Frequency:
        """Parse a frequency such as 'monthly'; raises InvalidChoiceError."""
        return _parse(cls, text, label="frequency", field="frequency")

    def next_date(self, d: date) -> date:
        """Return the next occurrence after d.

        WEEKLY adds 7 days. MONTHLY keeps the day of the month but clamps it to
        the month's length (31 Jan -> 28 Feb). YEARLY keeps the date but turns
        29 Feb into 28 Feb when the next year is not a leap year.

        Clamping is lossy, so chaining calls drifts:
        31 Jan -> 28 Feb -> 28 Mar. Recurring transactions must compute
        each occurrence from the original start date (the nth month after the
        start), not from the previous occurrence.
        """
        if self is Frequency.WEEKLY:
            return d + timedelta(days=7)
        if self is Frequency.MONTHLY:
            return add_month(d)
        return add_year(d)
