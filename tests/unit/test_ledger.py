import logging
from dataclasses import dataclass

import pytest

from pft.domain.category import AccountType
from pft.domain.exceptions import (
    AccountNotFoundError,
    CurrencyMismatchError,
    DuplicateTransactionError,
    TransactionNotFoundError,
)
from pft.domain.money import Money
from pft.services.ledger import (
    Ledger,
    LedgerEvent,
    TransactionAdded,
    TransactionRemoved,
)


@dataclass(frozen=True)
class StubTransaction:
    """Stand-in for #14's Transaction until it is merged."""

    id: int
    amount: Money

    def signed_amount(self) -> Money:
        return self.amount


class RecordingObserver:
    """Small test observer that records every event it receives."""

    def __init__(self) -> None:
        self.events: list[LedgerEvent] = []

    def update(self, event: LedgerEvent) -> None:
        self.events.append(event)


def tx(tx_id: int, amount: str) -> StubTransaction:
    return StubTransaction(tx_id, Money.of(amount))


def make_ledger() -> tuple[Ledger, int, int]:
    ledger = Ledger()
    bank = ledger.open_account("Bank", AccountType.BANK, Money.of("100.00"))
    cash = ledger.open_account("Cash", AccountType.CASH, Money.of("40.00"))
    return ledger, bank.id, cash.id


def test_net_worth_is_sum_of_all_balances() -> None:
    ledger, bank, cash = make_ledger()
    ledger.add_transaction(bank, tx(1, "-12.50"))
    ledger.add_transaction(cash, tx(2, "10.00"))
    assert ledger.net_worth == Money.of("137.50")
    assert ledger.net_worth == sum((a.balance for a in ledger.accounts), Money.zero())


def test_empty_ledger_net_worth_is_zero() -> None:
    assert Ledger().net_worth == Money.zero()


def test_account_ids_are_stable_and_never_reused() -> None:
    ledger, bank, _ = make_ledger()
    ledger.close_account(bank)
    assert ledger.open_account("New", AccountType.CARD, Money.zero()).id == 3


def test_unknown_account_id_raises() -> None:
    ledger = Ledger()
    with pytest.raises(AccountNotFoundError):
        ledger.account(99)
    with pytest.raises(AccountNotFoundError):
        ledger.add_transaction(99, tx(1, "5.00"))
    with pytest.raises(AccountNotFoundError):
        ledger.remove_transaction(99, 1)
    with pytest.raises(AccountNotFoundError):
        ledger.close_account(99)


def test_closed_account_is_gone_and_leaves_net_worth() -> None:
    ledger, bank, _ = make_ledger()
    closed = ledger.close_account(bank)
    assert closed.id == bank
    assert ledger.net_worth == Money.of("40.00")
    with pytest.raises(AccountNotFoundError):
        ledger.account(bank)


def test_observer_gets_exactly_one_event_per_added_transaction() -> None:
    ledger, bank, cash = make_ledger()
    observer = RecordingObserver()
    ledger.subscribe(observer)
    first, second = tx(1, "-5.00"), tx(2, "7.00")
    ledger.add_transaction(bank, first)
    ledger.add_transaction(cash, second)
    assert observer.events == [TransactionAdded(bank, first), TransactionAdded(cash, second)]


def test_remove_transaction_notifies_and_restores_balance() -> None:
    ledger, bank, _ = make_ledger()
    observer = RecordingObserver()
    ledger.add_transaction(bank, tx(1, "-5.00"))
    ledger.subscribe(observer)
    removed = ledger.remove_transaction(bank, 1)
    assert observer.events == [TransactionRemoved(bank, removed)]
    assert ledger.account(bank).balance == Money.of("100.00")


def test_unsubscribed_observer_gets_nothing_more() -> None:
    ledger, bank, _ = make_ledger()
    observer = RecordingObserver()
    ledger.subscribe(observer)
    ledger.unsubscribe(observer)
    ledger.unsubscribe(observer)  # unsubscribing twice is harmless
    ledger.add_transaction(bank, tx(1, "1.00"))
    assert observer.events == []


def test_subscribing_twice_still_gives_one_event() -> None:
    ledger, bank, _ = make_ledger()
    observer = RecordingObserver()
    ledger.subscribe(observer)
    ledger.subscribe(observer)
    ledger.add_transaction(bank, tx(1, "1.00"))
    assert len(observer.events) == 1


def test_all_observers_are_notified() -> None:
    ledger, bank, _ = make_ledger()
    first, second = RecordingObserver(), RecordingObserver()
    ledger.subscribe(first)
    ledger.subscribe(second)
    ledger.add_transaction(bank, tx(1, "1.00"))
    assert len(first.events) == len(second.events) == 1


def test_failed_change_sends_no_event_and_changes_nothing() -> None:
    ledger, bank, _ = make_ledger()
    observer = RecordingObserver()
    ledger.add_transaction(bank, tx(1, "1.00"))
    ledger.subscribe(observer)
    with pytest.raises(DuplicateTransactionError):
        ledger.add_transaction(bank, tx(1, "2.00"))
    with pytest.raises(TransactionNotFoundError):
        ledger.remove_transaction(bank, 99)
    with pytest.raises(CurrencyMismatchError):
        ledger.add_transaction(bank, StubTransaction(3, Money.of("1.00", "USD")))
    assert observer.events == []
    assert ledger.account(bank).balance == Money.of("101.00")


def test_all_transactions_walks_every_account_lazily() -> None:
    ledger, bank, cash = make_ledger()
    ledger.add_transaction(bank, tx(1, "1.00"))
    ledger.add_transaction(cash, tx(2, "2.00"))
    stream = ledger.all_transactions()
    assert iter(stream) is stream  # a generator-style iterator, not a list
    assert [t.id for t in stream] == [1, 2]


def test_observer_can_unsubscribe_itself_while_notified() -> None:
    ledger, bank, _ = make_ledger()

    class OneShot:
        def __init__(self) -> None:
            self.count = 0

        def update(self, event: LedgerEvent) -> None:
            self.count += 1
            ledger.unsubscribe(self)

    one_shot, other = OneShot(), RecordingObserver()
    ledger.subscribe(one_shot)
    ledger.subscribe(other)
    ledger.add_transaction(bank, tx(1, "1.00"))
    ledger.add_transaction(bank, tx(2, "1.00"))
    assert one_shot.count == 1
    assert len(other.events) == 2


class FailingObserver:
    def update(self, event: LedgerEvent) -> None:
        raise RuntimeError("observer bug")


def test_failing_observer_does_not_undo_or_hide_the_change(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ledger, bank, _ = make_ledger()
    before, after = RecordingObserver(), RecordingObserver()
    ledger.subscribe(before)
    ledger.subscribe(FailingObserver())
    ledger.subscribe(after)

    with caplog.at_level(logging.ERROR, logger="pft.services.ledger"):
        ledger.add_transaction(bank, tx(1, "-5.00"))  # must not raise

    # The mutation stands, and observers on both sides of the failing one were told.
    assert ledger.account(bank).balance == Money.of("95.00")
    assert len(before.events) == len(after.events) == 1
    assert "observer bug" in caplog.text


def test_failing_observer_does_not_break_remove_either() -> None:
    ledger, bank, _ = make_ledger()
    ledger.add_transaction(bank, tx(1, "-5.00"))
    after = RecordingObserver()
    ledger.subscribe(FailingObserver())
    ledger.subscribe(after)

    removed = ledger.remove_transaction(bank, 1)  # still returns the removed transaction

    assert removed.id == 1
    assert ledger.account(bank).balance == Money.of("100.00")
    assert after.events == [TransactionRemoved(bank, removed)]
