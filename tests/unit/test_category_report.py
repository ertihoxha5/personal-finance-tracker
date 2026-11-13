"""CategoryReport (#26): spending per category with each share of the total."""

import datetime as dt
from decimal import Decimal

import pytest

from pft.domain.category import Category
from pft.domain.exceptions import InvalidDateError
from pft.domain.money import Money
from pft.services.reports import CategoryReport, CategoryReportData, Report
from tests.unit.test_reports import Book

NOV_1 = dt.date(2026, 11, 1)
NOV_30 = dt.date(2026, 11, 30)


def build(book: Book, start: dt.date, end: dt.date) -> CategoryReportData:
    return CategoryReport(book.ledger, start, end).build()


def percent_sum(data: CategoryReportData) -> Decimal:
    return sum((c.percent for c in data.categories), Decimal("0.0"))


def test_amount_and_percent_per_category_largest_first() -> None:
    book = Book()
    book.expense("600.00", category=Category.RENT)
    book.expense("300.00", category=Category.FOOD)
    book.expense("100.00", category=Category.FUN)
    data = build(book, NOV_1, NOV_30)
    assert data.total == Money.of("1000.00")
    assert [(c.category, str(c.total.amount), str(c.percent)) for c in data.categories] == [
        (Category.RENT, "600.00", "60.0"),
        (Category.FOOD, "300.00", "30.0"),
        (Category.FUN, "100.00", "10.0"),
    ]


def test_same_category_is_added_up_and_ties_are_ordered_by_name() -> None:
    book = Book()
    book.expense("10.00", category=Category.FUN)
    book.expense("5.00", category=Category.FOOD)
    book.expense("5.00", category=Category.FOOD)
    book.expense("10.00", category=Category.BILLS)
    data = build(book, NOV_1, NOV_30)
    assert [c.category for c in data.categories] == [Category.BILLS, Category.FOOD, Category.FUN]
    assert all(c.total == Money.of("10.00") for c in data.categories)


def test_income_transfers_and_zero_spending_categories_are_hidden() -> None:
    book = Book()
    book.income("2000.00")
    book.transfer("250.00")
    book.expense("40.00", category=Category.HEALTH)
    data = build(book, NOV_1, NOV_30)
    assert [c.category for c in data.categories] == [Category.HEALTH]
    assert data.total == Money.of("40.00")
    assert data.categories[0].percent == Decimal("100.0")


@pytest.mark.parametrize(
    "amounts",
    [
        ["1.00", "1.00", "1.00"],  # three equal thirds: 33.3 x 3 would give 99.9
        ["2.00"] * 7,  # sevenths: 14.3 x 7 would give 100.1
        ["0.01", "999.99"],  # a tiny share still adds up
        ["12.34", "56.78", "9.01", "300.00", "0.99", "47.11", "5.55", "88.88", "1.23"],
    ],
)
def test_percentages_add_up_to_100(amounts: list[str]) -> None:
    book = Book()
    for amount, category in zip(amounts, list(Category), strict=False):
        book.expense(amount, category=category)
    data = build(book, NOV_1, NOV_30)
    assert abs(percent_sum(data) - Decimal("100.0")) <= Decimal("0.1")
    assert percent_sum(data) == Decimal("100.0")  # the method actually gives the exact sum


def test_one_day_period() -> None:
    book = Book()
    day = dt.date(2026, 11, 10)
    book.expense("30.00", day, Category.FOOD)
    book.expense("10.00", day, Category.FUN)
    book.expense("999.00", dt.date(2026, 11, 9), Category.RENT)
    book.expense("999.00", dt.date(2026, 11, 11), Category.RENT)
    data = build(book, day, day)
    assert [(c.category, str(c.percent)) for c in data.categories] == [
        (Category.FOOD, "75.0"),
        (Category.FUN, "25.0"),
    ]
    assert data.total == Money.of("40.00")


def test_full_year_includes_both_ends_and_nothing_outside() -> None:
    book = Book()
    book.expense("10.00", dt.date(2026, 1, 1), Category.FOOD)  # first day counts
    book.expense("10.00", dt.date(2026, 6, 15), Category.FOOD)
    book.expense("20.00", dt.date(2026, 12, 31), Category.RENT)  # last day counts
    book.expense("500.00", dt.date(2025, 12, 31), Category.FUN)
    book.expense("500.00", dt.date(2027, 1, 1), Category.FUN)
    data = build(book, dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert data.total == Money.of("40.00")
    assert [(c.category, str(c.percent)) for c in data.categories] == [
        (Category.FOOD, "50.0"),
        (Category.RENT, "50.0"),
    ]
    assert percent_sum(data) == Decimal("100.0")


def test_period_without_spending_gives_zero_total_and_no_categories() -> None:
    book = Book()
    book.income("100.00")
    data = build(book, NOV_1, NOV_30)
    assert data.total == Money.zero()
    assert data.categories == ()  # nothing to divide, so no division by zero either


def test_reversed_range_is_rejected_with_the_end_field() -> None:
    with pytest.raises(InvalidDateError) as caught:
        CategoryReport(Book().ledger, NOV_30, NOV_1)
    assert caught.value.field == "end"


def test_it_is_a_report_and_only_fills_in_the_two_steps() -> None:
    # Template Method: build() comes from Report; CategoryReport adds collect and summarize only.
    assert issubclass(CategoryReport, Report)
    assert "build" not in vars(CategoryReport)
    assert {"collect", "summarize"} <= set(vars(CategoryReport))
