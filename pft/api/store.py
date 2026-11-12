"""LedgerStore: one place where the API loads, changes and saves the Ledger (#18).

Every request reads the Ledger from the repository, and every change is saved before the
request answers, so a success response means the data is really stored. A lock makes
load-change-save one step, so two requests cannot overwrite each other's change. If saving
fails, the change disappears with the in-memory copy and the stored data is untouched.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TypeVar

from pft.infrastructure.repository import Repository, SqliteRepository
from pft.services.ledger import Ledger

T = TypeVar("T")


class LedgerStore:
    def __init__(self, repository: Repository) -> None:
        self._repository = repository
        self._lock = threading.Lock()

    def read(self, action: Callable[[Ledger], T]) -> T:
        """Run ``action`` on a freshly loaded Ledger without saving."""
        with self._lock:
            return action(self._repository.load())

    def write(self, action: Callable[[Ledger], T]) -> T:
        """Run ``action`` on a freshly loaded Ledger, then save it. Errors skip the save."""
        with self._lock:
            ledger = self._repository.load()
            result = action(ledger)
            self._repository.save(ledger)
            return result


_default_store: LedgerStore | None = None


def get_store() -> LedgerStore:
    """FastAPI dependency; tests override it with a store on a temporary database."""
    global _default_store
    if _default_store is None:
        _default_store = LedgerStore(SqliteRepository())
    return _default_store
