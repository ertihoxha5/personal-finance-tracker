"""Account entity.

An account owns its transactions and derives its balance from them, so the
balance can never drift out of sync with the list. The list is private and only
changes through add(), remove() and replace(), each of which keeps it consistent.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from pft.domain.category import AccountType
from pft.domain.exceptions import (
    CurrencyMismatchError,
    DuplicateTransactionError,
    InvalidAccountNameError,
    TransactionIdChangedError,
    TransactionNotFoundError,
)
from pft.domain.money import Money


class AccountTransaction(Protocol):
    """What an account needs from a transaction; #14's Transaction satisfies it."""

    @property
    def id(self) -> int: ...

    def signed_amount(self) -> Money: ...


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise InvalidAccountNameError("account name must not be empty")
    return cleaned


class Account:
    def __init__(
        self,
        id: int,
        name: str,
        type: AccountType,
        opening_balance: Money,
    ) -> None:
        self.id = id
        self._name = _clean_name(name)
        self.type = type
        self.opening_balance = opening_balance
        self._transactions: list[AccountTransaction] = []

    @property
    def name(self) -> str:
        return self._name

    def rename(self, new_name: str) -> None:
        self._name = _clean_name(new_name)

    @property
    def balance(self) -> Money:
        """Opening balance plus every transaction's signed amount."""
        return sum((t.signed_amount() for t in self._transactions), self.opening_balance)

    def add(self, transaction: AccountTransaction) -> None:
        self._check_currency(transaction)
        if transaction.id in self:
            raise DuplicateTransactionError(f"transaction {transaction.id} is already in account")
        self._transactions.append(transaction)

    def remove(self, tx_id: int) -> AccountTransaction:
        """Remove and return the transaction with this ID."""
        index = self._index_of(tx_id)
        return self._transactions.pop(index)

    def replace(self, tx_id: int, updated: AccountTransaction) -> None:
        """Edit a transaction by its stable ID (FR-04).

        The updated transaction must keep the same ID and take the old one's place
        in the list. Everything is validated before the list changes, so a failed
        edit leaves the account untouched.
        """
        index = self._index_of(tx_id)
        if updated.id != tx_id:
            raise TransactionIdChangedError(f"edit must keep ID {tx_id}, got {updated.id}")
        self._check_currency(updated)
        self._transactions[index] = updated

    def get(self, tx_id: int) -> AccountTransaction:
        return self._transactions[self._index_of(tx_id)]

    def _index_of(self, tx_id: int) -> int:
        for index, existing in enumerate(self._transactions):
            if existing.id == tx_id:
                return index
        raise TransactionNotFoundError(f"no transaction with ID {tx_id} in account {self.id}")

    def _check_currency(self, transaction: AccountTransaction) -> None:
        currency = transaction.signed_amount().currency
        if currency != self.opening_balance.currency:
            raise CurrencyMismatchError(
                f"cannot add a {currency} transaction to a {self.opening_balance.currency} account"
            )

    def __iter__(self) -> Iterator[AccountTransaction]:
        # Iterate a copy so callers cannot mutate the private list while looping.
        return iter(list(self._transactions))

    def __len__(self) -> int:
        return len(self._transactions)

    def __contains__(self, item: object) -> bool:
        """True for a transaction ID or for a transaction with an ID in this account."""
        tx_id = item if isinstance(item, int) else getattr(item, "id", None)
        return any(t.id == tx_id for t in self._transactions)

    def __repr__(self) -> str:
        return (
            f"Account(id={self.id!r}, name={self._name!r}, type={self.type.name}, "
            f"balance={self.balance})"
        )
