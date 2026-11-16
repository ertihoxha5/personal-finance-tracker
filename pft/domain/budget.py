"""Budget: a monthly spending limit for one category (#27, FR-15).

A ``Budget`` is a value: a category, a month written as ``2026-11`` and a positive limit.
It works out how much of the limit is used by reading the expenses of anything shaped
like the Ledger (``HasTransactions``). It never changes the Ledger, and the Ledger never
imports this module: budgets watch the Ledger, the Ledger does not know they exist.

Rules:

- Only ``Expense`` objects in the budget's category and month count. Income and transfers
  never use up a budget.
- Only expenses in the limit's currency count; another currency cannot be added to it.
- ``usage`` is a percentage rounded **down** to one decimal, so 99.99% never shows as 100%
  before the limit is really reached. The thresholds are compared on exact amounts.
- ``BUDGET_WARNING`` (80%) and ``BUDGET_EXCEEDED`` (100%) are the two warning levels used by
  ``pft.services.budget_monitor``.
- The year of the month must be ``MIN_YEAR`` to ``MAX_YEAR``. The reports use the same two
  constants, so a month that can hold a budget can always be reported.
- ``SentWarning`` records that a level of a budget was already reported. The records are
  stored (see pft.infrastructure.repository), so a level is reported once per budget even
  when the expense that reached it is deleted and added again.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import NamedTuple, Protocol

from pft.domain.category import Category
from pft.domain.exceptions import BudgetError, DataImportError, FinanceError
from pft.domain.money import Money
from pft.domain.transaction import Expense

BUDGET_WARNING = Decimal("0.80")
BUDGET_EXCEEDED = Decimal("1.00")
# Highest first, so the monitor reports the most serious level a single expense reaches.
BUDGET_LEVELS: tuple[Decimal, ...] = (BUDGET_EXCEEDED, BUDGET_WARNING)

# The years a budget or a report accepts. Reports also look at the month before and the one
# after, and the dashboard five months back; a year near 0001 or 9999 would make those dates
# impossible. pft.services.reports imports these, so both always agree.
MIN_YEAR = 1900
MAX_YEAR = 9998

_HUNDRED = Decimal(100)
_ONE_DECIMAL = Decimal("0.1")
_MONTH = re.compile(r"(\d{4})-(0[1-9]|1[0-2])")


class HasTransactions(Protocol):
    """What a budget needs from the Ledger (pft.services.ledger.Ledger fits)."""

    def all_transactions(self) -> Iterable[object]: ...


def level_percent(level: Decimal) -> int:
    """A level as a whole percentage: BUDGET_WARNING -> 80."""
    return int(level * _HUNDRED)


@dataclass(frozen=True)
class Budget:
    """A spending limit for one category in one month, for example FOOD, 2026-11, 200.00."""

    category: Category
    month: str
    limit: Money

    def __post_init__(self) -> None:
        if not isinstance(self.category, Category):
            raise BudgetError(
                f"category must be a Category, got {self.category!r}", field="category"
            )
        if not isinstance(self.month, str) or _MONTH.fullmatch(self.month) is None:
            raise BudgetError(f"invalid month {self.month!r}; use the form 2026-11", field="month")
        year = int(self.month[:4])
        if not MIN_YEAR <= year <= MAX_YEAR:
            raise BudgetError(f"year must be {MIN_YEAR} to {MAX_YEAR}, got {year}", field="month")
        if not isinstance(self.limit, Money) or self.limit.amount <= 0:
            raise BudgetError("a budget limit must be more than zero", field="limit")

    def covers(self, transaction: object) -> bool:
        """True for an expense in this budget's category, month and currency."""
        return (
            isinstance(transaction, Expense)
            and transaction.category is self.category
            and transaction.date.strftime("%Y-%m") == self.month
            and transaction.amount.currency == self.limit.currency
        )

    def spent(self, ledger: HasTransactions) -> Money:
        """The total of the expenses this budget covers."""
        total = Money.zero(self.limit.currency)
        for transaction in ledger.all_transactions():
            if isinstance(transaction, Expense) and self.covers(transaction):
                total += transaction.amount
        return total

    def remaining(self, ledger: HasTransactions) -> Money:
        """Limit minus spent; negative once the budget is exceeded."""
        return self.limit - self.spent(ledger)

    def usage(self, ledger: HasTransactions) -> Decimal:
        """Spent as a percentage of the limit, rounded down to one decimal (165/200 -> 82.5)."""
        return self.percent_of(self.spent(ledger))

    def percent_of(self, spent: Money) -> Decimal:
        """``spent`` as a percentage of the limit, rounded down to one decimal."""
        return (spent.amount / self.limit.amount * _HUNDRED).quantize(
            _ONE_DECIMAL, rounding=ROUND_DOWN
        )

    def has_reached(self, level: Decimal, spent: Money) -> bool:
        """True when ``spent`` is at or over ``level`` (0.80 = 80%) of the limit."""
        return spent.amount >= self.limit.amount * level

    def level_reached(self, spent: Money) -> Decimal | None:
        """The highest warning level ``spent`` is at or over, or None below 80%."""
        for level in BUDGET_LEVELS:
            if self.has_reached(level, spent):
                return level
        return None

    def is_exceeded(self, ledger: HasTransactions) -> bool:
        """True when the whole limit is used up (100% or more)."""
        return self.has_reached(BUDGET_EXCEEDED, self.spent(ledger))

    # --- storage: the BUDGET_COLUMNS of pft.infrastructure.repository -------------------

    def to_row(self) -> dict[str, str]:
        """The budget as text, keyed like BUDGET_COLUMNS."""
        return {
            "category": self.category.value,
            "month": self.month,
            "limit": str(self.limit.amount),
            "currency": self.limit.currency,
        }

    @classmethod
    def from_row(cls, row: Mapping[str, object]) -> Budget:
        """Rebuild a budget saved by to_row(), so ``from_row(b.to_row()) == b``."""
        try:
            return cls(
                Category.from_text(str(row["category"])),
                str(row["month"]).strip(),
                Money.of(str(row["limit"]), str(row["currency"])),
            )
        except KeyError as exc:
            raise DataImportError(f"budget row is missing column {exc}", field=str(exc)) from exc
        except FinanceError as exc:
            raise DataImportError(f"bad budget row: {exc.message}", field=exc.field) from exc


class SentWarning(NamedTuple):
    """A warning that was already sent: this level of the budget for this category and month."""

    category: Category
    month: str
    level: Decimal

    def to_row(self) -> dict[str, str]:
        """The record as text, keyed like SENT_WARNING_COLUMNS; the level is 80 or 100."""
        return {
            "category": self.category.value,
            "month": self.month,
            "level": str(level_percent(self.level)),
        }

    @classmethod
    def from_row(cls, row: Mapping[str, object]) -> SentWarning:
        """Rebuild a record saved by to_row(); an unknown level is a DataImportError."""
        try:
            percent = int(str(row["level"]))
            level = next(lv for lv in BUDGET_LEVELS if level_percent(lv) == percent)
            return cls(Category.from_text(str(row["category"])), str(row["month"]).strip(), level)
        except KeyError as exc:
            raise DataImportError(
                f"budget warning row is missing column {exc}", field=str(exc)
            ) from exc
        except (ValueError, StopIteration) as exc:
            raise DataImportError(f"bad budget warning level {row['level']!r}") from exc
        except FinanceError as exc:
            raise DataImportError(
                f"bad budget warning row: {exc.message}", field=exc.field
            ) from exc


__all__ = [
    "BUDGET_EXCEEDED",
    "BUDGET_LEVELS",
    "BUDGET_WARNING",
    "MAX_YEAR",
    "MIN_YEAR",
    "Budget",
    "HasTransactions",
    "SentWarning",
    "level_percent",
]
