"""Budget (#27): usage, thresholds, validation and storage rows. Synthetic data only."""

import datetime as dt
from decimal import Decimal

import pytest

from pft.domain.budget import BUDGET_EXCEEDED, BUDGET_WARNING, Budget, level_percent
from pft.domain.category import AccountType, Category
from pft.domain.exceptions import BudgetError, DataImportError
from pft.domain.money import Money
from pft.domain.transaction import Expense, Income
from pft.services.ledger import Ledger

NOVEMBER = "2026-11"


def make_ledger() -> Ledger:
    ledger = Ledger()
    ledger.open_account("Checking", AccountType.BANK, Money.of("1000.00"))
    ledger.open_account("Savings", AccountType.SAVINGS, Money.of("5000.00"))
    return ledger


def spend(
    ledger: Ledger,
    amount: str,
    category: Category = Category.FOOD,
    date: dt.date = dt.date(2026, 11, 10),
    account_id: int = 1,
) -> Expense:
    expense = Expense(
        id=ledger.next_transaction_id(),
        account_id=account_id,
        amount=Money.of(amount),
        date=date,
        category=category,
    )
    ledger.add_transaction(account_id, expense)
    return expense


def food_budget(limit: str = "200.00") -> Budget:
    return Budget(Category.FOOD, NOVEMBER, Money.of(limit))


def test_usage_is_spent_as_a_percentage_of_the_limit() -> None:
    ledger = make_ledger()
    spend(ledger, "150.00")
    spend(ledger, "15.00")
    budget = food_budget()
    assert budget.spent(ledger) == Money.of("165.00")
    assert budget.remaining(ledger) == Money.of("35.00")
    assert budget.usage(ledger) == Decimal("82.5")
    assert not budget.is_exceeded(ledger)


def test_only_expenses_of_the_same_category_and_month_count() -> None:
    ledger = make_ledger()
    spend(ledger, "40.00")
    spend(ledger, "60.00", category=Category.RENT)
    spend(ledger, "70.00", date=dt.date(2026, 10, 31))
    spend(ledger, "80.00", date=dt.date(2026, 12, 1))
    income = Income(
        id=ledger.next_transaction_id(),
        account_id=1,
        amount=Money.of("500.00"),
        date=dt.date(2026, 11, 5),
        category=Category.FOOD,
    )
    ledger.add_transaction(1, income)
    ledger.transfer(1, 2, Money.of("90.00"), dt.date(2026, 11, 6))
    assert food_budget().spent(ledger) == Money.of("40.00")


def test_expenses_of_every_account_count() -> None:
    ledger = make_ledger()
    spend(ledger, "30.00", account_id=1)
    spend(ledger, "20.00", account_id=2)
    assert food_budget().spent(ledger) == Money.of("50.00")


def test_usage_is_rounded_down_so_it_never_shows_100_too_early() -> None:
    ledger = make_ledger()
    spend(ledger, "199.99")
    budget = food_budget()
    assert budget.usage(ledger) == Decimal("99.9")
    assert not budget.is_exceeded(ledger)
    spend(ledger, "0.01")
    assert budget.usage(ledger) == Decimal("100.0")
    assert budget.is_exceeded(ledger)


def test_level_reached_uses_the_constants() -> None:
    budget = food_budget()
    assert (Decimal("0.80"), Decimal("1.00")) == (BUDGET_WARNING, BUDGET_EXCEEDED)
    assert (level_percent(BUDGET_WARNING), level_percent(BUDGET_EXCEEDED)) == (80, 100)
    assert budget.level_reached(Money.of("159.99")) is None
    assert budget.level_reached(Money.of("160.00")) == BUDGET_WARNING
    assert budget.level_reached(Money.of("199.99")) == BUDGET_WARNING
    assert budget.level_reached(Money.of("200.00")) == BUDGET_EXCEEDED


def test_an_empty_ledger_uses_nothing() -> None:
    assert food_budget().usage(Ledger()) == Decimal("0.0")


@pytest.mark.parametrize(
    ("month", "limit", "field"),
    [
        ("2026-13", "200.00", "month"),
        ("2026-1", "200.00", "month"),
        ("November", "200.00", "month"),
        (NOVEMBER, "0", "limit"),
        (NOVEMBER, "-5.00", "limit"),
    ],
)
def test_invalid_budgets_raise_budget_error(month: str, limit: str, field: str) -> None:
    with pytest.raises(BudgetError) as caught:
        Budget(Category.FOOD, month, Money.of(limit))
    assert caught.value.field == field
    assert caught.value.code == "budget_error"


def test_row_round_trip() -> None:
    budget = food_budget("300.00")
    row = budget.to_row()
    assert row == {"category": "food", "month": NOVEMBER, "limit": "300.00", "currency": "EUR"}
    assert Budget.from_row(row) == budget


def test_a_bad_stored_row_is_a_data_import_error() -> None:
    with pytest.raises(DataImportError):
        Budget.from_row({"category": "food", "month": NOVEMBER, "limit": "0", "currency": "EUR"})
    with pytest.raises(DataImportError):
        Budget.from_row({"category": "food", "month": NOVEMBER})
