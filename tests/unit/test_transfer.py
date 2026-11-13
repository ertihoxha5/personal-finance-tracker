"""Ledger.transfer (#23, FR-14): two linked rows, all or nothing. Synthetic data only."""

import datetime as dt

import pytest

from pft.domain.category import AccountType, Direction, Kind
from pft.domain.exceptions import (
    AccountNotFoundError,
    CurrencyMismatchError,
    InvalidAmountError,
    InvalidTransferError,
)
from pft.domain.money import Money
from pft.domain.transaction import Transfer
from pft.services.ledger import Ledger, LedgerEvent, TransactionAdded, TransactionRemoved

DAY = dt.date(2026, 11, 21)


class RecordingObserver:
    def __init__(self) -> None:
        self.events: list[LedgerEvent] = []

    def update(self, event: LedgerEvent) -> None:
        self.events.append(event)


@pytest.fixture
def ledger() -> Ledger:
    """Bank 100.00 (ID 1) and Cash 40.00 (ID 2), the plan's example."""
    ledger = Ledger()
    ledger.open_account("Bank", AccountType.BANK, Money.of("100.00"))
    ledger.open_account("Cash", AccountType.CASH, Money.of("40.00"))
    return ledger


def balances(ledger: Ledger) -> list[Money]:
    return [a.balance for a in ledger.accounts]


def test_transfer_moves_money_and_keeps_net_worth(ledger: Ledger) -> None:
    before = ledger.net_worth
    ledger.transfer(1, 2, Money.of("40.00"), DAY, "Cash for the market")
    assert balances(ledger) == [Money.of("60.00"), Money.of("80.00")]
    assert ledger.net_worth == before


def test_transfer_creates_two_linked_sides(ledger: Ledger) -> None:
    out_side, in_side = ledger.transfer(1, 2, Money.of("25.00"), DAY, "Top up")
    assert isinstance(out_side, Transfer) and isinstance(in_side, Transfer)
    assert (out_side.direction, in_side.direction) == (Direction.OUT, Direction.IN)
    assert (out_side.account_id, in_side.account_id) == (1, 2)
    assert out_side.transfer_id == in_side.transfer_id
    assert out_side.id != in_side.id
    assert out_side.kind is in_side.kind is Kind.TRANSFER
    assert out_side in ledger.account(1) and in_side in ledger.account(2)


def test_each_transfer_gets_its_own_id_and_new_row_ids(ledger: Ledger) -> None:
    first = ledger.transfer(1, 2, Money.of("10.00"), DAY)
    second = ledger.transfer(2, 1, Money.of("5.00"), DAY)
    assert first[0].transfer_id != second[0].transfer_id
    ids = [t.id for t in ledger.all_transactions()]
    assert len(ids) == len(set(ids)) == 4


def test_same_account_transfer_is_rejected(ledger: Ledger) -> None:
    with pytest.raises(InvalidTransferError) as info:
        ledger.transfer(1, 1, Money.of("10.00"), DAY)
    assert info.value.field == "to_account_id"
    assert len(list(ledger.all_transactions())) == 0


def test_transfer_above_balance_is_rejected(ledger: Ledger) -> None:
    with pytest.raises(InvalidTransferError) as info:
        ledger.transfer(2, 1, Money.of("40.01"), DAY)
    assert info.value.field == "amount"
    assert balances(ledger) == [Money.of("100.00"), Money.of("40.00")]


def test_transfer_of_the_whole_balance_is_allowed(ledger: Ledger) -> None:
    ledger.transfer(2, 1, Money.of("40.00"), DAY)
    assert ledger.account(2).balance == Money.zero()


@pytest.mark.parametrize("amount", ["0.00", "-5.00"])
def test_non_positive_amount_is_rejected(ledger: Ledger, amount: str) -> None:
    with pytest.raises(InvalidAmountError):
        ledger.transfer(1, 2, Money.of(amount), DAY)
    assert len(list(ledger.all_transactions())) == 0


def test_unknown_account_is_rejected_without_changes(ledger: Ledger) -> None:
    with pytest.raises(AccountNotFoundError):
        ledger.transfer(1, 99, Money.of("10.00"), DAY)
    assert len(list(ledger.all_transactions())) == 0


def test_failed_second_side_rolls_back_the_first(ledger: Ledger) -> None:
    """All or nothing: a USD account rejects the IN side, so the OUT side is removed."""
    ledger.open_account("US card", AccountType.CARD, Money.zero("USD"))
    observer = RecordingObserver()
    ledger.subscribe(observer)
    with pytest.raises(CurrencyMismatchError):
        ledger.transfer(1, 3, Money.of("10.00"), DAY)
    assert len(ledger.account(1)) == 0
    assert ledger.account(1).balance == Money.of("100.00")
    assert observer.events == []


def test_deleting_one_side_deletes_both(ledger: Ledger) -> None:
    out_side, in_side = ledger.transfer(1, 2, Money.of("30.00"), DAY)
    removed = ledger.remove_transaction(2, in_side.id)
    assert removed == in_side
    assert len(list(ledger.all_transactions())) == 0
    assert balances(ledger) == [Money.of("100.00"), Money.of("40.00")]


def test_observers_hear_both_sides(ledger: Ledger) -> None:
    observer = RecordingObserver()
    ledger.subscribe(observer)
    out_side, in_side = ledger.transfer(1, 2, Money.of("30.00"), DAY)
    ledger.remove_transaction(1, out_side.id)
    assert observer.events == [
        TransactionAdded(1, out_side),
        TransactionAdded(2, in_side),
        TransactionRemoved(1, out_side),
        TransactionRemoved(2, in_side),
    ]


def test_deleting_a_side_whose_partner_is_gone_removes_only_it(ledger: Ledger) -> None:
    """A lone side (e.g. loaded from a damaged file) is still removable."""
    lone = Transfer(
        id=7,
        account_id=1,
        amount=Money.of("5.00"),
        date=DAY,
        direction=Direction.OUT,
        transfer_id="orphan",
    )
    ledger.add_transaction(1, lone)
    assert ledger.remove_transaction(1, 7) == lone
    assert ledger.account(1).balance == Money.of("100.00")
