"""BudgetMonitor (#27): an Observer of the Ledger that warns at 80% and 100%.

The scenario from the plan: FOOD budget 200.00, spent 150.00, new expense 15.00.
"""

import datetime as dt
from decimal import Decimal
from pathlib import Path

from pft.domain.budget import BUDGET_EXCEEDED, BUDGET_WARNING, Budget
from pft.domain.category import AccountType, Category
from pft.domain.money import Money
from pft.domain.transaction import Expense, Income
from pft.services.budget_monitor import BudgetMonitor, BudgetWarning
from pft.services.ledger import Ledger

NOVEMBER = "2026-11"
FOOD_200 = Budget(Category.FOOD, NOVEMBER, Money.of("200.00"))


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
) -> Expense:
    expense = Expense(
        id=ledger.next_transaction_id(),
        account_id=1,
        amount=Money.of(amount),
        date=date,
        category=category,
    )
    ledger.add_transaction(1, expense)
    return expense


def watch(ledger: Ledger, *budgets: Budget) -> list[BudgetWarning]:
    """Subscribe a monitor for ``budgets`` and return the list its warnings go to."""
    warnings: list[BudgetWarning] = []
    ledger.subscribe(BudgetMonitor(ledger, budgets or [FOOD_200], warnings.append))
    return warnings


def messages(warnings: list[BudgetWarning]) -> list[str]:
    return [w.message for w in warnings]


def test_plan_scenario_150_plus_15_of_200_warns_at_82_percent() -> None:
    ledger = make_ledger()
    warnings = watch(ledger)
    spend(ledger, "150.00")
    assert warnings == []  # 75% is below the first level
    spend(ledger, "15.00")
    assert messages(warnings) == ["FOOD budget at 82%"]
    assert warnings[0].level == BUDGET_WARNING
    assert warnings[0].usage == Decimal("82.5")


def test_income_never_creates_a_warning() -> None:
    ledger = make_ledger()
    warnings = watch(ledger)
    spend(ledger, "150.00")
    income = Income(
        id=ledger.next_transaction_id(),
        account_id=1,
        amount=Money.of("900.00"),
        date=dt.date(2026, 11, 11),
        category=Category.FOOD,
    )
    ledger.add_transaction(1, income)
    assert warnings == []


def test_a_transfer_never_creates_a_warning() -> None:
    ledger = make_ledger()
    warnings = watch(ledger, Budget(Category.OTHER, NOVEMBER, Money.of("10.00")))
    ledger.transfer(1, 2, Money.of("500.00"), dt.date(2026, 11, 11))
    assert warnings == []


def test_a_second_expense_above_80_does_not_repeat_the_warning() -> None:
    ledger = make_ledger()
    warnings = watch(ledger)
    spend(ledger, "165.00")
    spend(ledger, "10.00")  # 87.5%: still between the two levels
    spend(ledger, "5.00")  # 90%
    assert messages(warnings) == ["FOOD budget at 82%"]


def test_100_percent_is_a_second_warning_sent_once() -> None:
    ledger = make_ledger()
    warnings = watch(ledger)
    spend(ledger, "165.00")
    spend(ledger, "35.00")  # exactly 100%
    spend(ledger, "50.00")  # 125%: nothing new
    assert messages(warnings) == ["FOOD budget at 82%", "FOOD budget at 100%"]
    assert [w.level for w in warnings] == [BUDGET_WARNING, BUDGET_EXCEEDED]


def test_one_expense_that_passes_both_levels_sends_only_the_100_warning() -> None:
    ledger = make_ledger()
    warnings = watch(ledger)
    spend(ledger, "210.00")
    assert messages(warnings) == ["FOOD budget at 105%"]
    assert warnings[0].level == BUDGET_EXCEEDED


def test_other_categories_and_months_are_ignored() -> None:
    ledger = make_ledger()
    warnings = watch(ledger)
    spend(ledger, "500.00", category=Category.RENT)
    spend(ledger, "500.00", date=dt.date(2026, 12, 1))
    assert warnings == []


def test_each_budget_and_each_month_warn_on_their_own() -> None:
    ledger = make_ledger()
    december = Budget(Category.FOOD, "2026-12", Money.of("100.00"))
    rent = Budget(Category.RENT, NOVEMBER, Money.of("600.00"))
    warnings = watch(ledger, FOOD_200, december, rent)
    spend(ledger, "170.00")
    spend(ledger, "85.00", date=dt.date(2026, 12, 3))
    spend(ledger, "600.00", category=Category.RENT)
    assert messages(warnings) == [
        "FOOD budget at 85%",
        "FOOD budget at 85%",
        "RENT budget at 100%",
    ]
    assert [w.month for w in warnings] == [NOVEMBER, "2026-12", NOVEMBER]


def test_a_new_monitor_after_a_restart_does_not_repeat_old_warnings() -> None:
    ledger = make_ledger()
    watch(ledger)
    spend(ledger, "165.00")
    # A fresh monitor has an empty memory, like the API on every request.
    later = watch(ledger)
    spend(ledger, "5.00")
    assert later == []


def test_removing_and_adding_the_same_expense_again_does_not_repeat() -> None:
    ledger = make_ledger()
    warnings = watch(ledger)
    spend(ledger, "150.00")
    crossing = spend(ledger, "15.00")
    ledger.remove_transaction(1, crossing.id)
    spend(ledger, "15.00")
    assert messages(warnings) == ["FOOD budget at 82%"]


def test_the_ledger_knows_nothing_about_budgets() -> None:
    import pft.services.ledger as ledger_module

    source = Path(ledger_module.__file__).read_text(encoding="utf-8")
    assert "pft.domain.budget" not in source
    assert "budget_monitor" not in source


def test_warning_to_dict_is_the_api_shape() -> None:
    warning = BudgetWarning(Category.FOOD, NOVEMBER, BUDGET_WARNING, Decimal("82.5"))
    assert warning.to_dict() == {
        "category": "food",
        "month": NOVEMBER,
        "level": 80,
        "usage_percent": "82.5",
        "message": "FOOD budget at 82%",
    }
