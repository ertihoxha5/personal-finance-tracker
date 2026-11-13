"""Reports (#19): a Template Method base class and the monthly summary.

``Report.build()`` is the template method. It fixes the order of the steps (first
``collect()`` the transactions, then ``summarize()`` them) and subclasses fill in each step.
A new report (#26, #31) only writes those two methods and cannot change the order.

``MonthlySummary`` reports one month: income, expenses, net, savings rate, the top three
spending categories and how the month compares with the previous one. Transfers are ignored
(money moving between your own accounts is neither income nor spending), and a month with no
transactions gives zeros, not an error.

``CategoryReport`` (#26) answers "where does the money go?": spending per category for any
date range, each with its amount and its share of total spending, largest first. Categories
with no spending are left out.

Money is exact. Category totals are summed in a ``Counter`` of integer cents, so a total never
passes through a float, and the savings rate is rounded half-up to one decimal place.
"""

from __future__ import annotations

import datetime as dt
import re
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from itertools import islice
from typing import Generic, TypeVar

from pft.domain.category import Category, Kind
from pft.domain.exceptions import InvalidDateError
from pft.domain.money import Money
from pft.domain.transaction import Transaction
from pft.services.filters import any_of, apply_filters, between, by_kind
from pft.services.ledger import Ledger

TOP_CATEGORY_COUNT = 3
_MONTH = re.compile(r"(\d{4})-(0[1-9]|1[0-2])")
_ONE_DECIMAL = Decimal("0.1")
_TENTHS_IN_WHOLE = 1000  # 100.0 percent, counted in steps of 0.1


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


def parse_month(text: str) -> tuple[int, int]:
    """Read a month typed as 2026-11 into (2026, 11); anything else is an InvalidDateError."""
    match = _MONTH.fullmatch(text.strip())
    if match is None:
        raise InvalidDateError(f"invalid month {text!r}; use the form 2026-11", field="month")
    return int(match[1]), int(match[2])


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


@dataclass(frozen=True)
class CategoryShare:
    """One category's spending and its share of all spending in the period."""

    category: Category
    total: Money
    percent: Decimal  # one decimal place; the shares of a report add up to exactly 100.0


@dataclass(frozen=True)
class CategoryReportData(ReportData):
    start: dt.date
    end: dt.date
    total: Money  # all spending in the period
    categories: tuple[CategoryShare, ...]  # largest first; categories with 0 spending are hidden


class CategoryReport(Report[CategoryReportData]):
    """Spending per category between two dates (both inclusive), with each share of the total."""

    def __init__(self, ledger: Ledger, start: dt.date, end: dt.date) -> None:
        if start > end:
            raise InvalidDateError("start date must be on or before end date", field="end")
        self._ledger = ledger
        self.start = start
        self.end = end

    def collect(self) -> Iterable[Transaction]:
        """Expenses in the period. Income and transfers are not spending."""
        rows = (t for t in self._ledger.all_transactions() if isinstance(t, Transaction))
        return apply_filters(rows, by_kind(Kind.EXPENSE), between(self.start, self.end))

    def summarize(self, rows: Iterable[Transaction]) -> CategoryReportData:
        spending: Counter[Category] = Counter()
        for t in rows:
            spending[t.category] += _cents(t.amount)
        # Largest first; equal totals are ordered by name, so input order never matters.
        ranked = [
            (category, cents)
            for category, cents in sorted(spending.items(), key=lambda i: (-i[1], i[0].value))
            if cents > 0
        ]
        total_cents = sum(cents for _, cents in ranked)
        tenths = _share_in_tenths([cents for _, cents in ranked], total_cents)
        categories = tuple(
            CategoryShare(category, _from_cents(cents), Decimal(tenth).scaleb(-1))
            for (category, cents), tenth in zip(ranked, tenths, strict=True)
        )
        return CategoryReportData(
            title=f"Spending by category {self.start.isoformat()} to {self.end.isoformat()}",
            start=self.start,
            end=self.end,
            total=_from_cents(total_cents),
            categories=categories,
        )


def _share_in_tenths(cents: list[int], total_cents: int) -> list[int]:
    """Each amount's share of the total in tenths of a percent, adding up to exactly 1000.

    Rounding every share on its own can leave the sum at 99.9 or 100.1. Instead every share is
    rounded down, and the tenths still missing go to the shares with the largest remainders
    (largest remainder method). Ties go to the earlier, i.e. larger, category.
    """
    if total_cents == 0:
        return []
    shares = [divmod(c * _TENTHS_IN_WHOLE, total_cents) for c in cents]
    tenths = [whole for whole, _ in shares]
    missing = _TENTHS_IN_WHOLE - sum(tenths)
    by_remainder = sorted(range(len(shares)), key=lambda i: (-shares[i][1], i))
    for i in by_remainder[:missing]:
        tenths[i] += 1
    return tenths


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
    "CategoryReport",
    "CategoryReportData",
    "CategoryShare",
    "CategoryTotal",
    "MonthlySummary",
    "MonthlySummaryData",
    "PeriodTotals",
    "Report",
    "ReportData",
    "parse_month",
    "previous_month",
    "savings_rate",
]
