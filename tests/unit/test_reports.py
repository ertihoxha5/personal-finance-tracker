import datetime as dt
from collections.abc import Iterable
from decimal import Decimal

import pytest

from pft.domain.category import AccountType, Category, Direction
from pft.domain.money import Money
from pft.domain.transaction import Expense, Income, Transaction, Transfer
from pft.services.ledger import Ledger
from pft.services.reports import (
    MonthlySummary,
    MonthlySummaryData,
    Report,
    ReportData,
    previous_month,
    savings_rate,
)

NOV = dt.date(2026, 11, 10)
OCT = dt.date(2026, 10, 10)


class Book:
    """Builds a ledger with one account and hands out unique transaction IDs."""

    def __init__(self) -> None:
        self.ledger = Ledger()
        self.account = self.ledger.open_account("Bank", AccountType.BANK, Money.zero()).id
        self.other = self.ledger.open_account("Cash", AccountType.CASH, Money.zero()).id
        self._next = 1

    def income(self, amount: str, day: dt.date = NOV, category: Category = Category.SALARY) -> None:
        self._add(Income, amount, day, category)

    def expense(self, amount: str, day: dt.date = NOV, category: Category = Category.FOOD) -> None:
        self._add(Expense, amount, day, category)

    def transfer(self, amount: str, day: dt.date = NOV) -> None:
        for account, direction in ((self.account, Direction.OUT), (self.other, Direction.IN)):
            self.ledger.add_transaction(
                account,
                Transfer(
                    id=self._next,
                    account_id=account,
                    amount=Money.of(amount),
                    date=day,
                    direction=direction,
                    transfer_id=f"t{self._next}",
                ),
            )
            self._next += 1

    def _add(self, cls: type[Transaction], amount: str, day: dt.date, category: Category) -> None:
        self.ledger.add_transaction(
            self.account,
            cls(
                id=self._next,
                account_id=self.account,
                amount=Money.of(amount),
                date=day,
                category=category,
            ),
        )
        self._next += 1

    def summary(self, year: int = 2026, month: int = 11) -> MonthlySummaryData:
        return MonthlySummary(self.ledger, year, month).build()


def test_income_800_expenses_600_gives_net_200_and_25_percent() -> None:
    book = Book()
    book.income("800.00")
    book.expense("600.00")
    data = book.summary()
    assert data.totals.income == Money.of("800.00")
    assert data.totals.expenses == Money.of("600.00")
    assert data.totals.net == Money.of("200.00")
    assert data.totals.savings_rate == Decimal("25.0")


def test_empty_month_shows_zeros_not_an_error() -> None:
    data = Book().summary()
    assert data.totals.income == data.totals.expenses == data.totals.net == Money.zero()
    assert data.totals.savings_rate == Decimal("0.0")
    assert data.totals.transaction_count == 0
    assert data.categories == ()
    assert data.top_categories == ()


def test_transfers_do_not_change_the_result() -> None:
    book = Book()
    book.income("800.00")
    book.expense("600.00")
    before = book.summary()
    book.transfer("250.00")
    after = book.summary()
    assert after == before


def test_top_three_categories_largest_first_with_stable_ties() -> None:
    book = Book()
    book.expense("50.00", category=Category.FUN)
    book.expense("50.00", category=Category.BILLS)  # ties with fun: ordered by name
    book.expense("10.00", category=Category.FOOD)
    book.expense("10.00", category=Category.FOOD)
    book.expense("5.00", category=Category.HEALTH)
    book.expense("200.00", category=Category.RENT)
    data = book.summary()
    assert [(c.category, str(c.total.amount)) for c in data.top_categories] == [
        (Category.RENT, "200.00"),
        (Category.BILLS, "50.00"),
        (Category.FUN, "50.00"),
    ]
    assert len(data.categories) == 5  # the full list is kept for the dashboard chart


def test_difference_to_previous_month() -> None:
    book = Book()
    book.income("500.00", OCT)
    book.expense("300.00", OCT)
    book.income("800.00")
    book.expense("600.00")
    data = book.summary()
    assert data.previous.net == Money.of("200.00")
    assert data.income_change == Money.of("300.00")
    assert data.expenses_change == Money.of("300.00")
    assert data.net_change == Money.zero()


def test_only_the_chosen_and_previous_month_are_used() -> None:
    book = Book()
    book.expense("999.00", dt.date(2026, 9, 30))
    book.expense("999.00", dt.date(2026, 12, 1))
    book.expense("10.00", dt.date(2026, 11, 30))  # last day of the month counts
    data = book.summary()
    assert data.totals.expenses == Money.of("10.00")
    assert data.previous.expenses == Money.zero()


def test_january_compares_with_december_of_the_year_before() -> None:
    assert previous_month(2026, 1) == (2025, 12)
    assert previous_month(2026, 7) == (2026, 6)
    book = Book()
    book.income("100.00", dt.date(2025, 12, 31))
    data = book.summary(2026, 1)
    assert (data.previous_year, data.previous_month) == (2025, 12)
    assert data.previous.income == Money.of("100.00")


def test_overspending_gives_a_negative_savings_rate() -> None:
    book = Book()
    book.income("100.00")
    book.expense("150.00")
    assert book.summary().totals.savings_rate == Decimal("-50.0")


def test_savings_rate_rounds_half_up_to_one_decimal() -> None:
    # 1 / 3 -> 33.3, and 0.05 of income rounds up, not to the even digit.
    assert savings_rate(Money.of("3.00"), Money.of("1.00")) == Decimal("33.3")
    assert savings_rate(Money.of("2000.00"), Money.of("1.00")) == Decimal("0.1")
    assert savings_rate(Money.zero(), Money.of("5.00")) == Decimal("0.0")


def test_invalid_month_is_rejected() -> None:
    with pytest.raises(ValueError, match="month must be 1 to 12"):
        MonthlySummary(Ledger(), 2026, 13)


def test_build_runs_collect_then_summarize() -> None:
    calls: list[str] = []

    class Spy(Report[ReportData]):
        def collect(self) -> Iterable[Transaction]:
            calls.append("collect")
            return []

        def summarize(self, rows: Iterable[Transaction]) -> ReportData:
            calls.append("summarize")
            return ReportData(title="spy")

    assert Spy().build().title == "spy"
    assert calls == ["collect", "summarize"]


def test_report_base_class_cannot_be_used_directly() -> None:
    with pytest.raises(TypeError):
        Report()  # type: ignore[abstract]
