from dataclasses import dataclass

import pytest

from pft.domain.account import Account
from pft.domain.category import AccountType
from pft.domain.exceptions import (
    CurrencyMismatchError,
    DuplicateTransactionError,
    FinanceError,
    InvalidAccountNameError,
    TransactionIdChangedError,
    TransactionNotFoundError,
)
from pft.domain.money import Money


@dataclass(frozen=True)
class StubTransaction:
    """Stand-in for #14's Transaction until it is merged."""

    id: int
    amount: Money

    def signed_amount(self) -> Money:
        return self.amount


def make_account(opening: str = "50.00") -> Account:
    return Account(1, "Checking", AccountType.BANK, Money.of(opening))


def expense(tx_id: int, amount: str) -> StubTransaction:
    return StubTransaction(tx_id, -Money.of(amount))


def test_new_account_balance_equals_opening_balance() -> None:
    assert make_account("50.00").balance == Money.of("50.00")


def test_negative_opening_balance_for_existing_debt() -> None:
    account = make_account("-250.00")
    assert account.balance == Money.of("-250.00")
    account.add(StubTransaction(1, Money.of("100.00")))  # a repayment
    assert account.balance == Money.of("-150.00")


def test_expense_reduces_balance() -> None:
    account = make_account("50.00")
    account.add(expense(1, "12.50"))
    assert account.balance == Money.of("37.50")


def test_remove_restores_balance_and_returns_transaction() -> None:
    account = make_account()
    tx = expense(1, "12.50")
    account.add(tx)
    assert account.remove(1) == tx
    assert account.balance == Money.of("50.00")


def test_remove_unknown_id_raises() -> None:
    with pytest.raises(TransactionNotFoundError):
        make_account().remove(99)


def test_iteration_len_and_contains() -> None:
    account = make_account()
    first, second = expense(1, "1.00"), expense(2, "2.00")
    account.add(first)
    account.add(second)
    assert list(account) == [first, second]
    assert len(account) == 2
    assert first in account
    assert 2 in account
    assert 3 not in account


def test_transactions_cannot_be_changed_from_outside() -> None:
    account = make_account()
    account.add(expense(1, "1.00"))
    for _ in account:
        account.add(expense(2, "2.00"))  # mutating while iterating is safe
    assert len(account) == 2
    assert not hasattr(account, "transactions")


def test_rename_trims_and_rejects_blank() -> None:
    account = make_account()
    account.rename("  Daily spending ")
    assert account.name == "Daily spending"
    with pytest.raises(InvalidAccountNameError):
        account.rename("   ")
    assert account.name == "Daily spending"


def test_duplicate_id_is_rejected() -> None:
    account = make_account()
    account.add(expense(1, "1.00"))
    with pytest.raises(DuplicateTransactionError):
        account.add(expense(1, "5.00"))
    assert len(account) == 1


def test_wrong_currency_is_rejected() -> None:
    with pytest.raises(CurrencyMismatchError):
        make_account().add(StubTransaction(1, Money.of("5.00", "USD")))


def test_replace_edits_by_id_and_updates_balance() -> None:
    account = make_account("50.00")
    account.add(expense(1, "12.50"))
    account.add(expense(2, "3.00"))
    account.replace(1, expense(1, "20.00"))
    assert account.balance == Money.of("27.00")
    assert [t.id for t in account] == [1, 2]  # position is kept


def test_failed_replace_leaves_account_unchanged() -> None:
    account = make_account("50.00")
    account.add(expense(1, "12.50"))
    with pytest.raises(TransactionIdChangedError):
        account.replace(1, expense(7, "1.00"))
    with pytest.raises(TransactionNotFoundError):
        account.replace(9, expense(9, "1.00"))
    with pytest.raises(CurrencyMismatchError):
        account.replace(1, StubTransaction(1, Money.of("1.00", "USD")))
    assert account.balance == Money.of("37.50")


def test_repr_and_error_family() -> None:
    assert "Checking" in repr(make_account())
    assert issubclass(TransactionNotFoundError, FinanceError)
