"""Budget routes (#27, FR-15, FR-16).

Budgets are stored next to the Ledger (see pft.infrastructure.repository); usage is always
calculated here from the Ledger's expenses, never in React. Amounts are decimal strings,
``usage_percent`` is a decimal string rounded down to one decimal ("82.5"), and levels are
the whole numbers 80 and 100. Errors use the usual {code, message, field} shape.

Warnings come from two places:

- ``GET /api/budgets`` lists, for the chosen month, every budget that is at or over a level
  right now (``warnings``), so the screen can always show the current state.
- ``POST /api/transactions`` (pft.api.accounts) subscribes a BudgetMonitor to the Ledger and
  returns the warnings that this one new expense caused.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from pft.api.store import LedgerStore, get_store
from pft.domain.budget import BUDGET_EXCEEDED, BUDGET_WARNING, Budget, level_percent
from pft.domain.category import Category
from pft.domain.exceptions import BudgetError, InvalidAmountError
from pft.domain.money import Money
from pft.services.budget_monitor import BudgetWarning
from pft.services.ledger import Ledger

router = APIRouter(prefix="/api/budgets", tags=["budgets"])
Store = Annotated[LedgerStore, Depends(get_store)]

STATUS_OK = "ok"
STATUS_WARNING = "warning"
STATUS_EXCEEDED = "exceeded"


class BudgetInput(BaseModel):
    category: str
    month: str
    limit: str


def _limit(text: str) -> Money:
    try:
        return Money.of(text.strip())
    except InvalidAmountError as exc:
        raise InvalidAmountError(
            f"invalid limit {text!r}; enter a number like 200.00", field="limit"
        ) from exc


def budget_dto(budget: Budget, ledger: Ledger) -> dict[str, Any]:
    """The stored budget plus everything calculated from the Ledger's expenses."""
    spent = budget.spent(ledger)
    level = budget.level_reached(spent)
    if level is None:
        status = STATUS_OK
    else:
        status = STATUS_EXCEEDED if level == BUDGET_EXCEEDED else STATUS_WARNING
    return budget.to_row() | {
        "spent": str(spent.amount),
        "remaining": str((budget.limit - spent).amount),
        "usage_percent": str(budget.percent_of(spent)),
        "status": status,
        "level": None if level is None else level_percent(level),
    }


def _current_warnings(budgets: list[Budget], ledger: Ledger) -> list[dict[str, Any]]:
    warnings = []
    for budget in budgets:
        spent = budget.spent(ledger)
        level = budget.level_reached(spent)
        if level is not None:
            warning = BudgetWarning(budget.category, budget.month, level, budget.percent_of(spent))
            warnings.append(warning.to_dict())
    return warnings


@router.get("")
def list_budgets(store: Store, month: Annotated[str | None, Query()] = None) -> dict[str, Any]:
    """Budgets of one month (default: the current month) with usage, status and warnings."""
    chosen = month.strip() if month else store.today().strftime("%Y-%m")
    # Building a Budget runs the domain's month check, so a bad month is a BudgetError.
    Budget(Category.OTHER, chosen, Money.of(1))

    def build(ledger: Ledger) -> dict[str, Any]:
        in_month = sorted(
            (b for b in store.budgets() if b.month == chosen), key=lambda b: b.category.value
        )
        return {
            "month": chosen,
            "thresholds": {
                "warning": level_percent(BUDGET_WARNING),
                "exceeded": level_percent(BUDGET_EXCEEDED),
            },
            "budgets": [budget_dto(b, ledger) for b in in_month],
            "warnings": _current_warnings(in_month, ledger),
        }

    return store.read(build)


@router.put("")
def set_budget(body: BudgetInput, store: Store) -> dict[str, Any]:
    """Create the budget for a category and month, or replace its limit if it exists."""
    budget = Budget(Category.from_text(body.category), body.month.strip(), _limit(body.limit))

    def put(budgets: list[Budget]) -> None:
        budgets[:] = [
            b for b in budgets if (b.category, b.month) != (budget.category, budget.month)
        ]
        budgets.append(budget)

    store.change_budgets(put)
    return store.read(lambda ledger: budget_dto(budget, ledger))


@router.delete("/{month}/{category}")
def delete_budget(month: str, category: str, store: Store) -> dict[str, str]:
    wanted = (Category.from_text(category), month)

    def remove(budgets: list[Budget]) -> None:
        kept = [b for b in budgets if (b.category, b.month) != wanted]
        if len(kept) == len(budgets):
            raise BudgetError(f"there is no {wanted[0].value} budget for {month}", field="category")
        budgets[:] = kept

    store.change_budgets(remove)
    return {"category": wanted[0].value, "month": month}
