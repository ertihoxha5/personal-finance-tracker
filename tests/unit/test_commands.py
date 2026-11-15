"""Optional Command pattern undo/redo, including linked transfers and failures."""

import datetime as dt

import pytest

from pft.domain.category import AccountType, Category
from pft.domain.exceptions import FinanceError
from pft.domain.money import Money
from pft.domain.transaction import Expense
from pft.services.commands import AddCommand, CommandError, DeleteCommand, History, TransferCommand
from pft.services.ledger import Ledger

DAY = dt.date(2026, 11, 15)


@pytest.fixture
def ledger() -> Ledger:
    ledger = Ledger()
    ledger.open_account("Bank", AccountType.BANK, Money.of("200.00"))
    ledger.open_account("Savings", AccountType.SAVINGS, Money.of("100.00"))
    return ledger


def expense(tx_id: int = 1) -> Expense:
    return Expense(
        id=tx_id,
        account_id=1,
        amount=Money.of("12.50"),
        date=DAY,
        category=Category.FOOD,
        note="Lunch",
    )


def test_add_undo_redo_preserves_identity_and_balance(ledger: Ledger) -> None:
    history = History()
    history.execute(AddCommand(ledger, expense()))
    assert ledger.account(1).balance == Money.of("187.50")
    history.undo()
    assert list(ledger.all_transactions()) == []
    assert ledger.account(1).balance == Money.of("200.00")
    history.redo()
    assert list(ledger.all_transactions()) == [expense()]
    assert ledger.account(1).balance == Money.of("187.50")


def test_delete_undo_redo(ledger: Ledger) -> None:
    ledger.add_transaction(1, expense())
    history = History()
    history.execute(DeleteCommand(ledger, 1, 1))
    assert list(ledger.all_transactions()) == []
    history.undo()
    assert list(ledger.all_transactions()) == [expense()]
    history.redo()
    assert list(ledger.all_transactions()) == []


def test_transfer_undo_redo_restores_both_original_linked_rows(ledger: Ledger) -> None:
    history = History()
    history.execute(TransferCommand(ledger, 1, 2, Money.of("50.00"), DAY))
    original = list(ledger.all_transactions())
    assert len(original) == 2
    assert ledger.account(1).balance == Money.of("150.00")
    assert ledger.account(2).balance == Money.of("150.00")
    history.undo()
    assert list(ledger.all_transactions()) == []
    history.redo()
    assert list(ledger.all_transactions()) == original
    assert ledger.net_worth == Money.of("300.00")


def test_delete_transfer_leg_and_undo_restores_entire_pair(ledger: Ledger) -> None:
    out_side, in_side = ledger.transfer(1, 2, Money.of("50.00"), DAY)
    history = History()
    history.execute(DeleteCommand(ledger, 2, in_side.id))
    assert list(ledger.all_transactions()) == []
    history.undo()
    assert list(ledger.all_transactions()) == [out_side, in_side]
    history.redo()
    assert list(ledger.all_transactions()) == []


def test_history_is_lifo_and_new_operation_discards_redo(ledger: Ledger) -> None:
    history = History()
    history.execute(AddCommand(ledger, expense(1)))
    history.execute(AddCommand(ledger, expense(2)))
    history.undo()
    assert [t.id for t in ledger.all_transactions()] == [1]
    assert history.can_redo
    history.execute(AddCommand(ledger, expense(3)))
    assert not history.can_redo
    history.undo()
    history.undo()
    assert not history.can_undo


@pytest.mark.parametrize("operation", ["undo", "redo"])
def test_empty_history_fails_cleanly(operation: str) -> None:
    with pytest.raises(CommandError, match="Nothing to"):
        getattr(History(), operation)()


def test_failed_execution_does_not_clear_redo(ledger: Ledger) -> None:
    history = History()
    history.execute(AddCommand(ledger, expense()))
    history.undo()
    with pytest.raises(FinanceError):
        history.execute(TransferCommand(ledger, 1, 2, Money.of("999.00"), DAY))
    assert history.can_redo
    assert not history.can_undo
    assert list(ledger.all_transactions()) == []


def test_failed_undo_does_not_move_stacks_or_overwrite_external_edit(ledger: Ledger) -> None:
    history = History()
    history.execute(AddCommand(ledger, expense()))
    changed = next(iter(ledger.account(1)))
    assert isinstance(changed, Expense)
    changed.note = "Edited externally"
    with pytest.raises(CommandError, match="outside this history"):
        history.undo()
    assert history.can_undo and not history.can_redo
    assert changed.note == "Edited externally"


def test_failed_redo_keeps_redo_stack(ledger: Ledger) -> None:
    history = History()
    history.execute(TransferCommand(ledger, 1, 2, Money.of("150.00"), DAY))
    history.undo()
    ledger.add_transaction(
        1, Expense(id=10, account_id=1, amount=Money.of("100.00"), date=DAY, category=Category.FOOD)
    )
    with pytest.raises(FinanceError, match="Insufficient"):
        history.redo()
    assert history.can_redo and not history.can_undo
    assert len(list(ledger.all_transactions())) == 1


def test_missing_target_account_prevents_partial_transfer_restore(ledger: Ledger) -> None:
    ledger.transfer(1, 2, Money.of("50.00"), DAY)
    history = History()
    history.execute(DeleteCommand(ledger, 1, 1))
    ledger.close_account(2)
    with pytest.raises(FinanceError):
        history.undo()
    assert list(ledger.all_transactions()) == []
    assert history.can_undo


def test_command_owns_snapshot_not_callers_mutable_object(ledger: Ledger) -> None:
    original = expense()
    command = AddCommand(ledger, original)
    original.note = "Changed by caller"
    command.execute()
    stored = next(iter(ledger.account(1)))
    assert isinstance(stored, Expense)
    assert stored.note == "Lunch"
    with pytest.raises(CommandError, match="already"):
        command.execute()


def test_deleted_ids_are_not_allocated_to_new_records_during_undo(ledger: Ledger) -> None:
    history = History()
    history.execute(AddCommand(ledger, expense(10)))
    history.undo()
    assert ledger.next_transaction_id() == 11
    history.redo()
    assert ledger.next_transaction_id() == 11
