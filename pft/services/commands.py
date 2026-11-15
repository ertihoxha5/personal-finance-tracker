"""Optional, session-local Command history (#28); no changes to Ledger are needed.

Only operations made through one History belong to its two stacks. Failed operations
do not move the stacks. A fresh successful command clears redo. History is deliberately
not persisted: restoring a repository starts a new session.
"""

from __future__ import annotations

import datetime as dt
from copy import copy, deepcopy
from typing import Protocol

from pft.domain.exceptions import FinanceError, InvalidTransferError, TransactionNotFoundError
from pft.domain.money import Money
from pft.domain.transaction import Transaction, Transfer
from pft.services.ledger import Ledger


class CommandError(FinanceError):
    """A history operation is unavailable or conflicts with external changes."""

    code = "command_error"


class Command(Protocol):
    ledger: Ledger

    def execute(self) -> None: ...

    def undo(self) -> None: ...


def _restore(ledger: Ledger, rows: tuple[Transaction, ...]) -> None:
    """Validate the entire set before restoring, including IDs across accounts."""
    existing = {t.id for t in ledger.all_transactions()}
    if len({t.id for t in rows}) != len(rows) or any(t.id in existing for t in rows):
        raise CommandError("Cannot restore transactions: an ID is already in use.")
    copies = {t.account_id: deepcopy(ledger.account(t.account_id)) for t in rows}
    for row in rows:
        copies[row.account_id].add(deepcopy(row))
    added: list[Transaction] = []
    try:
        for row in rows:
            ledger.add_transaction(row.account_id, deepcopy(row))
            added.append(row)
    except Exception:
        for row in reversed(added):
            if row.id in ledger.account(row.account_id):
                ledger.remove_transaction(row.account_id, row.id)
        raise


def _remove(ledger: Ledger, rows: tuple[Transaction, ...]) -> None:
    """Never undo over an external edit or a changed transfer pair."""
    current = {t.id: t for t in ledger.all_transactions()}
    if any(current.get(row.id) != row for row in rows):
        raise CommandError("Transactions changed outside this history; cannot undo or redo.")
    if isinstance(rows[0], Transfer):
        linked = {
            t.id
            for t in current.values()
            if isinstance(t, Transfer) and t.transfer_id == rows[0].transfer_id
        }
        if linked != {row.id for row in rows}:
            raise CommandError("The linked transfer changed outside this history.")
    ledger.remove_transaction(rows[0].account_id, rows[0].id)


class AddCommand:
    def __init__(self, ledger: Ledger, transaction: Transaction) -> None:
        if isinstance(transaction, Transfer):
            raise CommandError("Use TransferCommand to add a linked transfer.")
        self.ledger = ledger
        self.rows = (deepcopy(transaction),)
        self.applied = False

    def execute(self) -> None:
        if self.applied:
            raise CommandError("This command has already been executed.")
        _restore(self.ledger, self.rows)
        self.applied = True

    def undo(self) -> None:
        if not self.applied:
            raise CommandError("This command has not been executed.")
        _remove(self.ledger, self.rows)
        self.applied = False


class DeleteCommand:
    def __init__(self, ledger: Ledger, account_id: int, transaction_id: int) -> None:
        self.ledger = ledger
        self.account_id = account_id
        self.transaction_id = transaction_id
        self.rows: tuple[Transaction, ...] = ()
        self.applied = False

    def execute(self) -> None:
        if self.applied:
            raise CommandError("This command has already been executed.")
        if not self.rows:
            self.ledger.account(self.account_id)
            selected = next(
                (
                    t
                    for t in self.ledger.all_transactions()
                    if isinstance(t, Transaction)
                    and t.account_id == self.account_id
                    and t.id == self.transaction_id
                ),
                None,
            )
            if not isinstance(selected, Transaction):
                raise TransactionNotFoundError(f"no transaction with ID {self.transaction_id}")
            linked = [
                t
                for t in self.ledger.all_transactions()
                if isinstance(selected, Transfer)
                and isinstance(t, Transfer)
                and t.transfer_id == selected.transfer_id
                and t.id != selected.id
            ]
            if isinstance(selected, Transfer) and len(linked) != 1:
                raise CommandError("Cannot delete an incomplete transfer pair.")
            self.rows = tuple(deepcopy(t) for t in [selected, *linked])
        _remove(self.ledger, self.rows)
        self.applied = True

    def undo(self) -> None:
        if not self.applied:
            raise CommandError("This command has not been executed.")
        _restore(self.ledger, self.rows)
        self.applied = False


class TransferCommand:
    def __init__(
        self, ledger: Ledger, src: int, dst: int, money: Money, date: dt.date, note: str = ""
    ) -> None:
        self.ledger = ledger
        self.src, self.dst, self.money, self.date, self.note = src, dst, money, date, note
        self.rows: tuple[Transaction, ...] = ()
        self.applied = False

    def execute(self) -> None:
        if self.applied:
            raise CommandError("This command has already been executed.")
        if not self.rows:
            self.rows = tuple(
                deepcopy(t)
                for t in self.ledger.transfer(self.src, self.dst, self.money, self.date, self.note)
            )
        else:
            if self.ledger.account(self.src).balance < self.money:
                raise InvalidTransferError("Insufficient source balance to redo this transfer.")
            _restore(self.ledger, self.rows)
        self.applied = True

    def undo(self) -> None:
        if not self.applied:
            raise CommandError("This command has not been executed.")
        _remove(self.ledger, self.rows)
        self.applied = False


class History:
    """One session's undo and redo stacks; invoke only through these methods."""

    def __init__(self) -> None:
        self._undo: list[Command] = []
        self._redo: list[Command] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def fork(self, ledger: Ledger) -> History:
        """Stage history on a fresh ledger; publish it only after persistence succeeds."""
        result = History()
        for source, target in ((self._undo, result._undo), (self._redo, result._redo)):
            for command in source:
                staged = copy(command)
                staged.ledger = ledger
                target.append(staged)
        return result

    def execute(self, command: Command) -> None:
        command.execute()
        self._undo.append(command)
        self._redo.clear()

    def undo(self) -> None:
        if not self._undo:
            raise CommandError("Nothing to undo.")
        command = self._undo[-1]
        command.undo()
        self._undo.pop()
        self._redo.append(command)

    def redo(self) -> None:
        if not self._redo:
            raise CommandError("Nothing to redo.")
        command = self._redo[-1]
        command.execute()
        self._redo.pop()
        self._undo.append(command)
