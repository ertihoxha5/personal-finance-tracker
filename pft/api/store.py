"""LedgerStore: one place where the API loads, changes and saves the Ledger (#18).

Every request reads the Ledger from the repository, and every change is saved before the
request answers, so a success response means the data is really stored. A lock makes
load-change-save one step, so two requests cannot overwrite each other's change. If saving
fails, the change disappears with the in-memory copy and the stored data is untouched.

Budget warnings (#27): ``budget_monitor(ledger, callback)`` builds a BudgetMonitor that
already knows which warnings were sent before, and ``write`` saves what it sent after the
Ledger was saved. So a warning is sent once, even though every request has a new monitor.
"""

from __future__ import annotations

import datetime as dt
import threading
from collections.abc import Callable
from typing import TypeVar

from pft.domain.budget import Budget
from pft.infrastructure.repository import Repository, SqliteRepository
from pft.services.budget_monitor import BudgetMonitor, WarningCallback, forget_changed
from pft.services.ledger import Ledger

T = TypeVar("T")


class LedgerStore:
    def __init__(
        self, repository: Repository, today: Callable[[], dt.date] = dt.date.today
    ) -> None:
        self._repository = repository
        self._lock = threading.Lock()
        self._today = today
        self._monitors: list[BudgetMonitor] = []  # created during the current read/write

    def today(self) -> dt.date:
        """The date recurring rules are applied up to (replaceable in tests)."""
        return self._today()

    def _load(self) -> Ledger:
        """Load the Ledger and add any recurring items that became due (#25).

        Only missing items are added and last_run moves with them, so loading again (or
        after a restart) adds nothing. When something was added it is saved at once.
        """
        ledger = self._repository.load()
        if ledger.apply_recurring(self.today()):
            self._repository.save(ledger)
        return ledger

    def read(self, action: Callable[[Ledger], T]) -> T:
        """Run ``action`` on a freshly loaded Ledger without saving."""
        with self._lock:
            try:
                return action(self._load())
            finally:
                self._monitors.clear()  # nothing was saved, so nothing was sent for good

    def write(self, action: Callable[[Ledger], T]) -> T:
        """Run ``action`` on a freshly loaded Ledger, then save it. Errors skip the save.

        Warnings sent by a ``budget_monitor`` during ``action`` are remembered only after the
        Ledger was saved: if the save fails, the user never saw them and they can come again.
        """
        with self._lock:
            try:
                ledger = self._load()
                result = action(ledger)
                self._repository.save(ledger)
                self._remember_sent_warnings()
                return result
            finally:
                self._monitors.clear()

    def budget_monitor(self, ledger: Ledger, on_warning: WarningCallback) -> BudgetMonitor:
        """A BudgetMonitor for ``ledger`` that knows the stored budgets and warning history.

        Call it inside a ``write`` action and subscribe the result to the Ledger. Takes no lock.
        """
        monitor = BudgetMonitor(
            ledger,
            self._repository.load_budgets(),
            on_warning,
            self._repository.load_sent_warnings(),
        )
        self._monitors.append(monitor)
        return monitor

    def _remember_sent_warnings(self) -> None:
        if not self._monitors:
            return
        stored = self._repository.load_sent_warnings()
        sent = stored.union(*(monitor.sent for monitor in self._monitors))
        if sent != stored:
            self._repository.save_sent_warnings(sent)

    def budgets(self) -> list[Budget]:
        """The stored budgets (#27). Takes no lock, so it can be called inside read/write."""
        return self._repository.load_budgets()

    def change_budgets(self, action: Callable[[list[Budget]], T]) -> T:
        """Run ``action`` on the list of stored budgets, then save the list it changed.

        A budget that was removed or got another limit starts with an empty warning history.
        """
        with self._lock:
            budgets = self._repository.load_budgets()
            before = list(budgets)
            result = action(budgets)
            self._repository.save_budgets(budgets)
            stored = self._repository.load_sent_warnings()
            kept = forget_changed(stored, before, budgets)
            if kept != stored:
                self._repository.save_sent_warnings(kept)
            return result


_default_store: LedgerStore | None = None


def get_store() -> LedgerStore:
    """FastAPI dependency; tests override it with a store on a temporary database."""
    global _default_store
    if _default_store is None:
        _default_store = LedgerStore(SqliteRepository())
    return _default_store
