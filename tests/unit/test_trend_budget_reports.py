"""TrendReport and BudgetReport (#31): two reports on the #19 Template Method base class."""

import datetime as dt
from decimal import Decimal

import pytest

from pft.domain.budget import Budget
from pft.domain.category import AccountType, Category
from pft.domain.exceptions import InvalidDateError
from pft.domain.money import Money
from pft.domain.transaction import Expense, Income
from pft.services.ledger import Ledger
from pft.services.reports import (
    BudgetReport,
    BudgetStatus,
    MonthlySummary,
    Report,
    TrendReport,
)

NOVEMBER = "2026-11"


def make_ledger() -> Ledger:
    ledger = Ledger()
    ledger.open_account("Checking", AccountType.BANK, Money.of("5000.00"))
    ledger.open_account("Savings", AccountType.SAVINGS, Money.of("5000.00"))
    return ledger


def add(
    ledger: Ledger,
    kind: type[Income] | type[Expense],
    amount: str,
    date: dt.date,
    category: Category = Category.FOOD,
) -> None:
    transaction = kind(
        id=ledger.next_transaction_id(),
        account_id=1,
        amount=Money.of(amount),
        date=date,
        category=category,
    )
    ledger.add_transaction(1, transaction)


def budget(category: Category, limit: str, month: str = NOVEMBER) -> Budget:
    return Budget(category, month, Money.of(limit))


# --- TrendReport ---------------------------------------------------------------------------


def test_six_months_give_exactly_six_rows_in_date_order() -> None:
    ledger = make_ledger()
    add(ledger, Income, "2000.00", dt.date(2026, 11, 1), Category.SALARY)
    add(ledger, Expense, "600.00", dt.date(2026, 11, 3), Category.RENT)
    add(ledger, Expense, "150.00", dt.date(2026, 8, 20))
    add(ledger, Income, "1800.00", dt.date(2026, 6, 30), Category.SALARY)
    add(ledger, Expense, "999.00", dt.date(2026, 5, 31))  # one day before the range
    add(ledger, Expense, "999.00", dt.date(2026, 12, 1))  # one day after the range

    report = TrendReport(ledger, 6, 2026, 11).build()

    assert [(m.year, m.month) for m in report.months] == [
        (2026, 6),
        (2026, 7),
        (2026, 8),
        (2026, 9),
        (2026, 10),
        (2026, 11),
    ]
    by_month = {m.month: m for m in report.months}
    assert by_month[6].income == Money.of("1800.00")
    assert by_month[8].expenses == Money.of("150.00")
    assert by_month[8].net == Money.of("-150.00")
    assert by_month[11].net == Money.of("1400.00")
    assert report.title == "Trend 2026-06 to 2026-11"


def test_months_without_data_show_zero() -> None:
    report = TrendReport(make_ledger(), 3, 2026, 11).build()
    assert len(report.months) == 3
    zero = Money.zero()
    assert all((m.income, m.expenses, m.net) == (zero, zero, zero) for m in report.months)


def test_trend_crosses_a_year_boundary() -> None:
    report = TrendReport(make_ledger(), 4, 2027, 2).build()
    assert [(m.year, m.month) for m in report.months] == [
        (2026, 11),
        (2026, 12),
        (2027, 1),
        (2027, 2),
    ]


def test_trend_leaves_transfers_out() -> None:
    ledger = make_ledger()
    ledger.transfer(1, 2, Money.of("700.00"), dt.date(2026, 11, 5))
    [month] = TrendReport(ledger, 1, 2026, 11).build().months
    assert (month.income, month.expenses) == (Money.zero(), Money.zero())


def test_trend_agrees_with_monthly_summary() -> None:
    ledger = make_ledger()
    add(ledger, Income, "2000.00", dt.date(2026, 10, 1), Category.SALARY)
    add(ledger, Expense, "64.50", dt.date(2026, 10, 2))
    add(ledger, Expense, "0.10", dt.date(2026, 10, 3))
    add(ledger, Expense, "0.20", dt.date(2026, 10, 4))
    [october] = TrendReport(ledger, 1, 2026, 10).build().months
    summary = MonthlySummary(ledger, 2026, 10).build().totals
    assert (october.income, october.expenses, october.net) == (
        summary.income,
        summary.expenses,
        summary.net,
    )
    assert october.expenses == Money.of("64.80")  # exact: 0.1 + 0.2 is not 0.30000000000000004


@pytest.mark.parametrize("months", [0, -1, 121])
def test_trend_rejects_a_bad_number_of_months(months: int) -> None:
    with pytest.raises(ValueError, match="months must be"):
        TrendReport(make_ledger(), months, 2026, 11)


def test_trend_rejects_a_range_that_starts_before_the_earliest_year() -> None:
    with pytest.raises(InvalidDateError):
        TrendReport(make_ledger(), 6, 1900, 3)


# --- BudgetReport --------------------------------------------------------------------------


def test_planned_actual_and_difference_per_category() -> None:
    ledger = make_ledger()
    add(ledger, Expense, "150.00", dt.date(2026, 11, 10))
    add(ledger, Expense, "15.00", dt.date(2026, 11, 12))
    add(ledger, Expense, "600.00", dt.date(2026, 11, 3), Category.RENT)
    budgets = [budget(Category.RENT, "600.00"), budget(Category.FOOD, "200.00")]

    report = BudgetReport(ledger, budgets, NOVEMBER).build()

    food, rent = report.lines  # ordered by category name
    assert (food.category, food.planned, food.actual) == (
        Category.FOOD,
        Money.of("200.00"),
        Money.of("165.00"),
    )
    assert food.difference == Money.of("35.00")
    assert food.usage == Decimal("82.5")
    assert food.status is BudgetStatus.WARNING
    assert (rent.difference, rent.status) == (Money.zero(), BudgetStatus.OVER)
    assert (report.planned, report.actual, report.difference) == (
        Money.of("800.00"),
        Money.of("765.00"),
        Money.of("35.00"),
    )


@pytest.mark.parametrize(
    ("spent", "status"),
    [
        ("0.00", BudgetStatus.OK),
        ("159.99", BudgetStatus.OK),
        ("160.00", BudgetStatus.WARNING),  # exactly 80%
        ("199.99", BudgetStatus.WARNING),
        ("200.00", BudgetStatus.OVER),  # exactly 100%
        ("250.00", BudgetStatus.OVER),
    ],
)
def test_statuses_match_the_80_and_100_percent_limits(spent: str, status: BudgetStatus) -> None:
    ledger = make_ledger()
    if spent != "0.00":
        add(ledger, Expense, spent, dt.date(2026, 11, 10))
    [line] = BudgetReport(ledger, [budget(Category.FOOD, "200.00")], NOVEMBER).build().lines
    assert line.status is status


def test_overspending_gives_a_negative_difference() -> None:
    ledger = make_ledger()
    add(ledger, Expense, "210.00", dt.date(2026, 11, 10))
    report = BudgetReport(ledger, [budget(Category.FOOD, "200.00")], NOVEMBER).build()
    assert report.lines[0].difference == Money.of("-10.00")
    assert report.difference == Money.of("-10.00")


def test_only_the_months_own_budgets_and_expenses_count() -> None:
    ledger = make_ledger()
    add(ledger, Expense, "50.00", dt.date(2026, 11, 10))
    add(ledger, Expense, "70.00", dt.date(2026, 10, 31))
    add(ledger, Income, "900.00", dt.date(2026, 11, 11))
    add(ledger, Expense, "30.00", dt.date(2026, 11, 12), Category.FUN)  # no budget for fun
    ledger.transfer(1, 2, Money.of("400.00"), dt.date(2026, 11, 13))
    budgets = [budget(Category.FOOD, "200.00"), budget(Category.FOOD, "300.00", "2026-12")]

    report = BudgetReport(ledger, budgets, NOVEMBER).build()

    assert [(line.category, line.actual) for line in report.lines] == [
        (Category.FOOD, Money.of("50.00"))
    ]


def test_a_month_without_budgets_is_empty_not_an_error() -> None:
    report = BudgetReport(make_ledger(), [], NOVEMBER).build()
    assert report.lines == ()
    assert (report.planned, report.actual, report.difference) == (Money.zero(),) * 3


def test_budget_report_rejects_a_bad_month() -> None:
    with pytest.raises(InvalidDateError):
        BudgetReport(make_ledger(), [], "2026-13")


# --- Template Method -----------------------------------------------------------------------


@pytest.mark.parametrize("report_class", [TrendReport, BudgetReport])
def test_build_is_inherited_not_copied(report_class: type) -> None:
    assert issubclass(report_class, Report)
    assert "build" not in vars(report_class)  # the class body does not define build()
    assert report_class.build is Report.build
    assert {"collect", "summarize"} <= set(vars(report_class))
