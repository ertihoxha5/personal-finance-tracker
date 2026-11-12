"""Reports (#19): a Template Method base class and the monthly summary.

``Report.build()`` is the template method. It fixes the order of the steps (first
``collect()`` the transactions, then ``summarize()`` them) and subclasses fill in each step.
A new report (#26, #31) only writes those two methods and cannot change the order.

``MonthlySummary`` reports one month: income, expenses, net, savings rate, the top three
spending categories and how the month compares with the previous one. Transfers are ignored
(money moving between your own accounts is neither income nor spending), and a month with no
transactions gives zeros, not an error.

Money is exact. Category totals are summed in a ``Counter`` of integer cents, so a total never
passes through a float, and the savings rate is rounded half-up to one decimal place.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from itertools import islice
from typing import Generic, TypeVar

from pft.domain.category import Category, Kind
from pft.domain.money import Money
from pft.domain.transaction import Transaction
from pft.services.filters import any_of, apply_filters, between, by_kind
from pft.services.ledger import Ledger

TOP_CATEGORY_COUNT = 3
_ONE_DECIMAL = Decimal("0.1")


@dataclass(frozen=True)
class ReportData:
    """What every report returns. Subclasses add the fields their report needs."""

    title: str


D = TypeVar("D", bound=ReportData)


class Report(ABC, Generic[D]):
    """Template Method: ``build`` runs ``collect`` then ``summarize``, in that order."""

    def build(self) -> D:
        rows = self.collect()
        return self.summarize(rows)

    @abstractmethod
    def collect(self) -> Iterable[Transaction]:
        """Pick the transactions this report is about."""

    @abstractmethod
    def summarize(self, rows: Iterable[Transaction]) -> D:
        """Turn the collected transactions into the report's result."""


@dataclass(frozen=True)
class CategoryTotal:
    category: Category
    total: Money


@dataclass(frozen=True)
class PeriodTotals:
    """Income and spending of one month."""

    income: Money
    expenses: Money
    net: Money
    savings_rate: Decimal  # percent, one decimal place; 0.0 when there was no income
    transaction_count: int


@dataclass(frozen=True)
class MonthlySummaryData(ReportData):
    year: int
    month: int
    totals: PeriodTotals
    categories: tuple[CategoryTotal, ...]  # all spending categories, largest first
    previous_year: int
    previous_month: int
    previous: PeriodTotals

    @property
    def top_categories(self) -> tuple[CategoryTotal, ...]:
        """The three categories with the most spending."""
        return tuple(islice(self.categories, TOP_CATEGORY_COUNT))

    @property
    def income_change(self) -> Money:
        return self.totals.income - self.previous.income

    @property
    def expenses_change(self) -> Money:
        return self.totals.expenses - self.previous.expenses

    @property
    def net_change(self) -> Money:
        return self.totals.net - self.previous.net


def previous_month(year: int, month: int) -> tuple[int, int]:
    """The month before (year, month); January rolls back to December of the year before."""
    return (year - 1, 12) if month == 1 else (year, month - 1)


def savings_rate(income: Money, net: Money) -> Decimal:
    """Net as a percentage of income, one decimal, half-up. No income means 0.0, not an error."""
    if income.amount == 0:
        return Decimal("0.0")
    return (net.amount / income.amount * 100).quantize(_ONE_DECIMAL, rounding=ROUND_HALF_UP)


class MonthlySummary(Report[MonthlySummaryData]):
    """Income, expenses, net, savings rate, top categories and the change from last month."""

    def __init__(self, ledger: Ledger, year: int, month: int) -> None:
        if not 1 <= month <= 12:
            raise ValueError(f"month must be 1 to 12, got {month}")
        self._ledger = ledger
        self.year = year
        self.month = month
        self.previous_year, self.previous_month = previous_month(year, month)

    def collect(self) -> Iterable[Transaction]:
        """This month and the one before it, transfers left out, in one lazy pass."""
        first_previous = dt.date(self.previous_year, self.previous_month, 1)
        end = _last_day(self.year, self.month)
        rows = (t for t in self._ledger.all_transactions() if isinstance(t, Transaction))
        income_or_expense = any_of(by_kind(Kind.INCOME), by_kind(Kind.EXPENSE))
        return apply_filters(rows, income_or_expense, between(first_previous, end))

    def summarize(self, rows: Iterable[Transaction]) -> MonthlySummaryData:
        current: list[Transaction] = []
        earlier: list[Transaction] = []
        for t in rows:
            in_current = (t.date.year, t.date.month) == (self.year, self.month)
            (current if in_current else earlier).append(t)

        spending: Counter[Category] = Counter()
        for t in current:
            if t.kind is Kind.EXPENSE:
                spending[t.category] += _cents(t.amount)
        # Largest first; equal totals are ordered by name, so input order never matters.
        ranked = sorted(spending.items(), key=lambda item: (-item[1], item[0].value))
        categories = tuple(CategoryTotal(c, _from_cents(total)) for c, total in ranked)

        return MonthlySummaryData(
            title=f"Monthly summary {self.year}-{self.month:02d}",
            year=self.year,
            month=self.month,
            totals=_totals(current),
            categories=categories,
            previous_year=self.previous_year,
            previous_month=self.previous_month,
            previous=_totals(earlier),
        )


def _last_day(year: int, month: int) -> dt.date:
    first_next = dt.date(year + 1, 1, 1) if month == 12 else dt.date(year, month + 1, 1)
    return first_next - dt.timedelta(days=1)


def _cents(money: Money) -> int:
    return int(money.amount.scaleb(2))


def _from_cents(cents: int) -> Money:
    return Money.of(Decimal(cents).scaleb(-2))


def _totals(rows: list[Transaction]) -> PeriodTotals:
    income = sum((t.amount for t in rows if t.kind is Kind.INCOME), Money.zero())
    expenses = sum((t.amount for t in rows if t.kind is Kind.EXPENSE), Money.zero())
    net = income - expenses
    return PeriodTotals(income, expenses, net, savings_rate(income, net), len(rows))


__all__ = [
    "CategoryTotal",
    "MonthlySummary",
    "MonthlySummaryData",
    "PeriodTotals",
    "Report",
    "ReportData",
    "previous_month",
    "savings_rate",
]
