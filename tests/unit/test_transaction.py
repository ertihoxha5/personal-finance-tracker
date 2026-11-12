import dataclasses
import datetime as dt
from typing import Any, cast

import pytest

from pft.domain.account import Account
from pft.domain.category import AccountType, Category, Direction, Kind
from pft.domain.exceptions import (
    InvalidAmountError,
    InvalidCategoryError,
    InvalidChoiceError,
    InvalidDateError,
    InvalidTextError,
    InvalidTransferError,
)
from pft.domain.money import Money
from pft.domain.transaction import CSV_COLUMNS, Expense, Income, Transaction, Transfer

DAY = dt.date(2026, 11, 15)


def income(amount: str = "2200.00", *, tx_id: int = 1, date: dt.date = DAY) -> Income:
    return Income(
        id=tx_id,
        account_id=1,
        amount=Money.of(amount),
        date=date,
        category=Category.SALARY,
        note="Monthly salary",
    )


def expense(amount: str = "64.50", *, tx_id: int = 2, date: dt.date = DAY) -> Expense:
    return Expense(
        id=tx_id,
        account_id=1,
        amount=Money.of(amount),
        date=date,
        category=Category.FOOD,
        note="Weekly groceries",
    )


def transfer(direction: Direction, amount: str = "300.00", *, tx_id: int = 3) -> Transfer:
    return Transfer(
        id=tx_id,
        account_id=1 if direction is Direction.OUT else 2,
        amount=Money.of(amount),
        date=DAY,
        direction=direction,
        transfer_id="tr-1",
    )


# --- Abstraction ----------------------------------------------------------------------


def test_transaction_itself_cannot_be_created() -> None:
    with pytest.raises(TypeError, match="abstract"):
        Transaction(  # type: ignore[abstract]
            id=1, account_id=1, amount=Money.of("1"), date=DAY, category=Category.FOOD
        )


def test_positional_construction_is_rejected() -> None:
    with pytest.raises(TypeError):
        Expense(1, 1, Money.of("1"), DAY, Category.FOOD)  # type: ignore[call-arg]


# --- Signed amounts and kind (polymorphism) ---------------------------------------------


@pytest.mark.parametrize(
    ("make", "signed", "kind"),
    [
        (lambda: income("10"), "10.00", Kind.INCOME),
        (lambda: expense("10"), "-10.00", Kind.EXPENSE),
        (lambda: transfer(Direction.OUT, "10"), "-10.00", Kind.TRANSFER),
        (lambda: transfer(Direction.IN, "10"), "10.00", Kind.TRANSFER),
    ],
    ids=["income", "expense", "transfer-out", "transfer-in"],
)
def test_signed_amount_and_kind(make: Any, signed: str, kind: Kind) -> None:
    transaction = make()
    assert transaction.signed_amount() == Money.of(signed)
    assert transaction.kind is kind
    assert transaction.amount == Money.of("10")  # the stored amount stays positive


def test_mixed_list_totals_through_signed_amount() -> None:
    mixed: list[Transaction] = [
        income("2200.00"),
        expense("64.50"),
        expense("600.00", tx_id=4),
        transfer(Direction.OUT, "300.00"),
        transfer(Direction.IN, "300.00", tx_id=5),
    ]
    total = sum((t.signed_amount() for t in mixed), Money.zero())
    assert total == Money.of("1535.50")


def test_works_with_account_balance() -> None:
    account = Account(1, "Checking", AccountType.BANK, Money.of("100.00"))
    account.add(income("50.00"))
    account.add(expense("30.00"))
    assert account.balance == Money.of("120.00")


# --- Validation -----------------------------------------------------------------------


@pytest.mark.parametrize("amount", ["0", "-5"])
def test_zero_or_negative_amount_is_rejected(amount: str) -> None:
    with pytest.raises(InvalidAmountError, match="amount must be greater than zero"):
        expense(amount)


def test_assigning_a_negative_amount_later_is_rejected() -> None:
    item = expense("10")
    with pytest.raises(InvalidAmountError):
        item.amount = Money.of("-10")
    assert item.amount == Money.of("10")


def test_missing_amount_is_a_type_error() -> None:
    # mypy believes amount has a default (the descriptor); at runtime it is required.
    with pytest.raises(TypeError, match="amount"):
        Expense(id=1, account_id=1, date=DAY, category=Category.FOOD)


@pytest.mark.parametrize(
    "value",
    [dt.datetime(2026, 11, 15, 9, 30), "2026-11-15", None],
    ids=["datetime", "string", "none"],
)
def test_date_must_be_a_plain_date(value: object) -> None:
    with pytest.raises(InvalidDateError) as caught:
        expense(date=cast(dt.date, value))
    assert caught.value.field == "date"


def test_category_must_be_a_category_member() -> None:
    with pytest.raises(InvalidCategoryError):
        Expense(id=1, account_id=1, amount=Money.of("1"), date=DAY, category=cast(Category, "food"))


def test_note_is_optional_stripped_and_text_only() -> None:
    plain = Expense(id=1, account_id=1, amount=Money.of("1"), date=DAY, category=Category.FOOD)
    assert plain.note == ""
    assert dataclasses.replace(plain, note="  Lunch  ").note == "Lunch"
    with pytest.raises(InvalidTextError):
        dataclasses.replace(plain, note=cast(str, 42))


def test_transfer_needs_direction_and_transfer_id() -> None:
    base: dict[str, Any] = {"id": 1, "account_id": 1, "amount": Money.of("1"), "date": DAY}
    with pytest.raises(TypeError, match="direction"):
        Transfer(**base, transfer_id="tr-1")
    with pytest.raises(TypeError, match="transfer_id"):
        Transfer(**base, direction=Direction.OUT)
    with pytest.raises(InvalidTextError):
        Transfer(**base, direction=Direction.OUT, transfer_id="  ")
    with pytest.raises(InvalidChoiceError):
        Transfer(**base, direction=cast(Direction, "sideways"), transfer_id="tr-1")


def test_transfer_category_defaults_to_other() -> None:
    assert transfer(Direction.OUT).category is Category.OTHER


# --- to_row ---------------------------------------------------------------------------


def test_to_row_has_exactly_the_agreed_columns_in_order() -> None:
    for item in (income(), expense(), transfer(Direction.OUT)):
        row = item.to_row()
        assert tuple(row) == CSV_COLUMNS
        assert all(isinstance(value, str) for value in row.values())


def test_to_row_values() -> None:
    assert expense().to_row() == {
        "id": "2",
        "account_id": "1",
        "kind": "expense",
        "amount": "64.50",
        "currency": "EUR",
        "date": "2026-11-15",
        "category": "food",
        "note": "Weekly groceries",
        "transfer_id": "",
        "direction": "",
    }
    row = transfer(Direction.IN).to_row()
    assert (row["kind"], row["amount"], row["transfer_id"], row["direction"]) == (
        "transfer",
        "300.00",
        "tr-1",
        "in",
    )


# --- Ordering, equality, copy_for -------------------------------------------------------


def test_sorted_orders_by_date_and_keeps_ties_stable() -> None:
    late = expense(date=dt.date(2026, 11, 30), tx_id=10)
    early = income(date=dt.date(2026, 11, 1), tx_id=11)
    same_day_a = expense(date=DAY, tx_id=12)
    same_day_b = income(date=DAY, tx_id=13)
    ordered = sorted([late, same_day_a, early, same_day_b])
    assert [t.id for t in ordered] == [11, 12, 13, 10]


def test_less_than_a_non_transaction_is_a_type_error() -> None:
    with pytest.raises(TypeError):
        _ = expense() < cast(Any, DAY)


def test_equality_compares_all_fields_and_transactions_are_unhashable() -> None:
    assert expense() == expense()
    assert expense() != expense(tx_id=99)
    assert cast(Transaction, income("10")) != expense("10")
    with pytest.raises(TypeError):
        hash(expense())


def test_copy_for_gives_a_new_id_and_date_and_leaves_the_original() -> None:
    original = expense()
    copy = original.copy_for(dt.date(2026, 12, 15), new_id=50)
    assert isinstance(copy, Expense)
    assert (copy.id, copy.date) == (50, dt.date(2026, 12, 15))
    assert (copy.amount, copy.category, copy.note) == (
        original.amount,
        original.category,
        original.note,
    )
    assert (original.id, original.date) == (2, DAY)


def test_copy_for_validates_the_new_date() -> None:
    with pytest.raises(InvalidDateError):
        income().copy_for(cast(dt.date, dt.datetime(2026, 12, 1)), new_id=51)


def test_transfer_cannot_be_copied() -> None:
    with pytest.raises(InvalidTransferError, match="recurring transfers are not supported"):
        transfer(Direction.OUT).copy_for(dt.date(2026, 12, 5), new_id=52)
