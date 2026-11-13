"""Ledger: the central service that holds every account.

The Ledger owns accounts by composition and tells subscribed observers (such as a
budget monitor) when a transaction is added or removed, without knowing who they are.
It never prints and never touches files; persistence and output belong to other layers.

Observer failures: a change is final before observers are told, so an observer that raises
is logged and skipped. The change stands, the caller sees no error, and later observers
still get the event.
"""

from __future__ import annotations

import datetime as dt
import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import chain
from typing import Protocol

from pft.domain.account import Account, AccountTransaction
from pft.domain.category import AccountType, Direction
from pft.domain.exceptions import AccountNotFoundError, DataImportError, InvalidTransferError
from pft.domain.money import Money
from pft.domain.transaction import Transfer

logger = logging.getLogger(__name__)


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

    def restore_account(self, account: Account) -> None:
        """Add an account that already has its stored ID (used by repositories when loading).

        The next new ID moves past every restored one, so IDs stay unique.
        """
        if account.id in self._accounts:
            raise DataImportError(f"account ID {account.id} appears twice", field="id")
        self._accounts[account.id] = account
        self._next_account_id = max(self._next_account_id, account.id + 1)

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
        """Remove and return a transaction. Removing one side of a transfer removes both (#23)."""
        removed = self.account(account_id).remove(tx_id)
        events = [TransactionRemoved(account_id, removed)]
        if isinstance(removed, Transfer):
            other = self._counterpart(removed)
            if other is not None:
                self.account(other.account_id).remove(other.id)
                events.append(TransactionRemoved(other.account_id, other))
        for event in events:
            self._notify(event)
        return removed

    def next_transaction_id(self) -> int:
        """One more than the highest transaction ID in any account (1 when there are none)."""
        return max((t.id for t in self.all_transactions()), default=0) + 1

    def transfer(
        self,
        src: int,
        dst: int,
        money: Money,
        date: dt.date,
        note: str = "",
    ) -> tuple[Transfer, Transfer]:
        """Move money between two accounts as two linked Transfer rows (#23, FR-14).

        The OUT side goes to ``src`` and the IN side to ``dst``; both share one
        ``transfer_id``. It is all or nothing: if the second row cannot be added,
        the first is taken out again, so no half-transfer is ever left behind.
        Net worth does not change. Returns ``(out_side, in_side)``.
        """
        if src == dst:
            raise InvalidTransferError(
                "choose two different accounts for a transfer", field="to_account_id"
            )
        source, target = self.account(src), self.account(dst)
        transfer_id = uuid.uuid4().hex
        first_id = self.next_transaction_id()

        def side(tx_id: int, account_id: int, direction: Direction) -> Transfer:
            return Transfer(
                id=tx_id,
                account_id=account_id,
                amount=money,
                date=date,
                note=note,
                direction=direction,
                transfer_id=transfer_id,
            )

        # Building both rows first runs every field check (amount, date, note) up front.
        out_side = side(first_id, src, Direction.OUT)
        in_side = side(first_id + 1, dst, Direction.IN)
        if source.balance + out_side.signed_amount() < Money.zero(source.balance.currency):
            raise InvalidTransferError(
                f"the transfer is more than the {source.balance} in {source.name}", field="amount"
            )

        source.add(out_side)
        try:
            target.add(in_side)
        except Exception:
            source.remove(out_side.id)
            raise
        # Observers only hear about a transfer once both sides are in place.
        self._notify(TransactionAdded(src, out_side))
        self._notify(TransactionAdded(dst, in_side))
        return out_side, in_side

    def all_transactions(self) -> Iterator[AccountTransaction]:
        """Every transaction of every account, one after another, without building a list."""
        return chain.from_iterable(self._accounts.values())

    def _counterpart(self, side: Transfer) -> Transfer | None:
        """The other row of the same transfer, or None if it is already gone."""
        for t in self.all_transactions():
            if isinstance(t, Transfer) and t.transfer_id == side.transfer_id and t.id != side.id:
                return t
        return None

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
        """Tell every observer; one observer failing never affects the others or the caller.

        By the time observers hear about a change it has already happened, so an observer
        error must not make add_transaction/remove_transaction look as if it failed.
        The failure is logged with its traceback and the next observer is still notified.
        """
        # Loop over a copy so an observer can unsubscribe itself while being notified.
        for observer in list(self._observers):
            try:
                observer.update(event)
            except Exception:
                logger.exception("observer %r failed on %s", observer, type(event).__name__)
