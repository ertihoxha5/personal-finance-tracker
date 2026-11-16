"""BudgetMonitor: warns when spending reaches 80% or 100% of a budget (#27, FR-16).

Observer pattern: the monitor has ``update(event)``, so it fits the Ledger's ``Observer``
protocol and is added with ``ledger.subscribe(monitor)``. The Ledger only knows "someone
wants to hear about changes"; everything about budgets lives here and in
``pft.domain.budget``. Removing the monitor changes nothing in the Ledger.

The monitor never prints. Each warning goes to the callback it was given: the CLI passes
a function that prints, the API passes ``list.append`` and returns the warnings as JSON.

A level is reported once per budget (category and month):

- A warning is sent only by the expense that **crosses** the level: spending was below it
  before this expense and is at or above it after. A later expense above 80% crosses
  nothing, so it is silent. This needs no saved state, so it also holds after a restart,
  when a new monitor is created.
- The monitor also remembers what it sent (``sent``), so removing the crossing expense and
  adding it again does not repeat a warning. That memory is **saved**: whoever creates the
  monitor passes in the stored history and saves ``monitor.sent`` afterwards (the API does it
  in ``LedgerStore``, the CLI after saving the Ledger). Without that, a new monitor, which
  the API builds for every request, would have forgotten and warned a second time.
- The history of a budget is forgotten when the budget is removed or its limit changes
  (``forget_changed``): 80% of a new limit is a different amount, so it is a new warning.

One expense that jumps from under 80% straight past 100% sends only the 100% warning.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal

from pft.domain.budget import (
    BUDGET_LEVELS,
    Budget,
    HasTransactions,
    SentWarning,
    level_percent,
)
from pft.domain.category import Category
from pft.domain.transaction import Expense
from pft.services.ledger import LedgerEvent, TransactionAdded


@dataclass(frozen=True)
class BudgetWarning:
    """One warning: which budget, which level (0.80 or 1.00) and the usage that caused it."""

    category: Category
    month: str
    level: Decimal
    usage: Decimal

    @property
    def message(self) -> str:
        """For example 'FOOD budget at 82%' (the percentage is rounded down)."""
        return f"{self.category.name} budget at {int(self.usage)}%"

    def to_dict(self) -> dict[str, str | int]:
        """The API shape; ``level`` is 80 or 100 and ``usage_percent`` a decimal string."""
        return {
            "category": self.category.value,
            "month": self.month,
            "level": level_percent(self.level),
            "usage_percent": str(self.usage),
            "message": self.message,
        }


WarningCallback = Callable[[BudgetWarning], None]


class BudgetMonitor:
    """An Observer of the Ledger that turns new expenses into budget warnings."""

    def __init__(
        self,
        ledger: HasTransactions,
        budgets: Iterable[Budget],
        on_warning: WarningCallback,
        sent: Iterable[SentWarning] = (),
    ) -> None:
        self._ledger = ledger
        self._budgets = list(budgets)
        self._on_warning = on_warning
        self._sent: set[SentWarning] = set(sent)

    @property
    def sent(self) -> frozenset[SentWarning]:
        """Every level already reported: the history passed in plus what this monitor sent.

        Save it after the change is stored and pass it to the next monitor.
        """
        return frozenset(self._sent)

    def update(self, event: LedgerEvent) -> None:
        """Called by the Ledger after every change; only a new expense can cause a warning."""
        if not isinstance(event, TransactionAdded):
            return
        expense = event.transaction
        if not isinstance(expense, Expense):
            return  # income and transfers never use up a budget
        for budget in self._budgets:
            if budget.covers(expense):
                self._check(budget, expense)

    def _check(self, budget: Budget, expense: Expense) -> None:
        after = budget.spent(self._ledger)  # the Ledger already contains the new expense
        before = after - expense.amount
        crossed = [
            level
            for level in BUDGET_LEVELS
            if budget.has_reached(level, after) and not budget.has_reached(level, before)
        ]
        if not crossed:
            return
        top = crossed[0]  # BUDGET_LEVELS is highest first
        already_sent = SentWarning(budget.category, budget.month, top) in self._sent
        # Reaching a level also covers the lower ones, so they are never sent afterwards.
        self._sent.update(SentWarning(budget.category, budget.month, level) for level in crossed)
        if not already_sent:
            self._on_warning(
                BudgetWarning(budget.category, budget.month, top, budget.percent_of(after))
            )


def forget_changed(
    sent: Iterable[SentWarning], before: Iterable[Budget], after: Iterable[Budget]
) -> set[SentWarning]:
    """``sent`` without the records of budgets that were removed or got another limit.

    A budget that is unchanged keeps its history, so saving the same limit again does not
    bring an old warning back.
    """
    limits_before = {(b.category, b.month): b.limit for b in before}
    limits_after = {(b.category, b.month): b.limit for b in after}
    kept: set[SentWarning] = set()
    for record in sent:
        key = (record.category, record.month)
        if key not in limits_before or limits_before[key] == limits_after.get(key):
            kept.add(record)
    return kept


__all__ = ["BudgetMonitor", "BudgetWarning", "WarningCallback", "forget_changed"]
