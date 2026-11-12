"""Ledger: the central service that holds every account.

The Ledger owns accounts by composition and tells subscribed observers (such as a
budget monitor) when a transaction is added or removed, without knowing who they are.
It never prints and never touches files; persistence and output belong to other layers.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import chain
from typing import Protocol

from pft.domain.account import Account, AccountTransaction
from pft.domain.category import AccountType
from pft.domain.exceptions import AccountNotFoundError
from pft.domain.money import Money


@dataclass(frozen=True)
class TransactionAdded:
    account_id: int
    transaction: AccountTransaction


@dataclass(frozen=True)
class TransactionRemoved:
    account_id: int
    transaction: AccountTransaction


LedgerEvent = TransactionAdded | TransactionRemoved


class Observer(Protocol):
    """Anything with update(event) can subscribe; no base class needed."""

    def update(self, event: LedgerEvent) -> None: ...


class Ledger:
    def __init__(self) -> None:
        self._accounts: dict[int, Account] = {}
        self._observers: list[Observer] = []
        self._next_account_id = 1

    # --- accounts -----------------------------------------------------------

    def open_account(self, name: str, type: AccountType, opening_balance: Money) -> Account:
        """Create an account with a new stable ID. IDs are never reused."""
        account = Account(self._next_account_id, name, type, opening_balance)
        self._accounts[account.id] = account
        self._next_account_id += 1
        return account

    def close_account(self, account_id: int) -> Account:
        """Remove and return the account. Observers are not told; only transactions notify."""
        account = self.account(account_id)
        del self._accounts[account_id]
        return account

    def account(self, account_id: int) -> Account:
        try:
            return self._accounts[account_id]
        except KeyError:
            raise AccountNotFoundError(f"no account with ID {account_id}") from None

    @property
    def accounts(self) -> list[Account]:
        """A copy, so callers cannot change the private dictionary."""
        return list(self._accounts.values())

    # --- transactions -------------------------------------------------------

    def add_transaction(self, account_id: int, transaction: AccountTransaction) -> None:
        # The account validates first; observers only hear about changes that happened.
        self.account(account_id).add(transaction)
        self._notify(TransactionAdded(account_id, transaction))

    def remove_transaction(self, account_id: int, tx_id: int) -> AccountTransaction:
        removed = self.account(account_id).remove(tx_id)
        self._notify(TransactionRemoved(account_id, removed))
        return removed

    def all_transactions(self) -> Iterator[AccountTransaction]:
        """Every transaction of every account, one after another, without building a list."""
        return chain.from_iterable(self._accounts.values())

    @property
    def net_worth(self) -> Money:
        """Sum of all account balances. An empty ledger is zero in the default currency."""
        return sum((a.balance for a in self._accounts.values()), Money.zero())

    # --- observers ----------------------------------------------------------

    def subscribe(self, observer: Observer) -> None:
        # Ignoring repeats keeps it to one event per observer per change.
        if observer not in self._observers:
            self._observers.append(observer)

    def unsubscribe(self, observer: Observer) -> None:
        """Stop notifying the observer. Does nothing if it was not subscribed."""
        if observer in self._observers:
            self._observers.remove(observer)

    def _notify(self, event: LedgerEvent) -> None:
        # Loop over a copy so an observer can unsubscribe itself while being notified.
        for observer in list(self._observers):
            observer.update(event)
