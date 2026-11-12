import datetime as dt
from decimal import Decimal

import pytest

from pft.domain.category import Category, Direction, Kind
from pft.domain.exceptions import (
    DataImportError,
    InvalidAmountError,
    InvalidCategoryError,
    InvalidChoiceError,
    InvalidCurrencyError,
    InvalidDateError,
    InvalidTransferError,
)
from pft.domain.factory import TransactionFactory
from pft.domain.money import Money
from pft.domain.transaction import CSV_COLUMNS, Expense, Income, Transaction, Transfer

DAY = dt.date(2026, 11, 17)


def make(
    kind: str,
    amount: str = "12.50",
    date: str = "2026-11-17",
    *,
    category: str = "food",
    note: str = "",
) -> Transaction:
    return TransactionFactory.from_input(kind, amount, category, date, 1, note, transaction_id=7)


def transfer(direction: Direction) -> Transfer:
    return Transfer(
        id=11 if direction is Direction.OUT else 12,
        account_id=1 if direction is Direction.OUT else 2,
        amount=Money.of("300.00"),
        date=DAY,
        direction=direction,
        transfer_id="tr-1",
        note="Move to savings",
    )


SAMPLES: list[Transaction] = [
    Income(
        id=1,
        account_id=1,
        amount=Money.of("2200"),
        date=DAY,
        category=Category.SALARY,
        note="Monthly salary",
    ),
    Expense(
        id=2,
        account_id=1,
        amount=Money.of("64.50"),
        date=DAY,
        category=Category.FOOD,
        note="Weekly groceries",
    ),
    transfer(Direction.OUT),
    transfer(Direction.IN),
]


# --- Done-when tests -------------------------------------------------------------


@pytest.mark.parametrize(
    "original", SAMPLES, ids=["income", "expense", "transfer-out", "transfer-in"]
)
def test_round_trip_through_row(original: Transaction) -> None:
    rebuilt = TransactionFactory.from_row(original.to_row())
    assert rebuilt == original
    assert type(rebuilt) is type(original)


def test_decimal_comma_is_accepted() -> None:
    t = make("expense", "12,50")
    assert isinstance(t, Expense)
    assert t.amount == Money.of("12.50")


def test_text_amount_raises_invalid_amount() -> None:
    with pytest.raises(InvalidAmountError) as info:
        make("expense", "abc")
    assert info.value.field == "amount"


def test_wrong_date_raises_invalid_date() -> None:
    with pytest.raises(InvalidDateError) as info:
        make("expense", date="2026-13-40")
    assert "2026-13-40" in info.value.message


def test_from_input_builds_income_with_parsed_fields() -> None:
    t = make(" Income ", "2200", category=" SALARY ", note="  Monthly salary ")
    assert t == Income(
        id=7,
        account_id=1,
        amount=Money.of("2200.00"),
        date=DAY,
        category=Category.SALARY,
        note="Monthly salary",
    )


# --- Amount and date parsing ----------------------------------------------------


@pytest.mark.parametrize(
    "text", ["1.234,50", "1,234.50", "1,234,50", "12,505", "12.505", "", "  ", ".", "1e3"]
)
def test_ambiguous_or_malformed_amounts_are_rejected(text: str) -> None:
    with pytest.raises(InvalidAmountError):
        make("expense", text)


@pytest.mark.parametrize("text", ["0", "0,00", "-5", "-5,00"])
def test_zero_and_negative_amounts_are_rejected(text: str) -> None:
    with pytest.raises(InvalidAmountError):
        make("expense", text)


@pytest.mark.parametrize(
    "text,expected", [(" 12,5 ", "12.50"), ("7", "7.00"), (",5", "0.50"), ("12.", "12.00")]
)
def test_amount_spaces_trimmed_and_normalised(text: str, expected: str) -> None:
    assert make("expense", text).amount.amount == Decimal(expected)


@pytest.mark.parametrize(
    "text", ["2026-13-40", "17/11/2026", "20261117", "2026-11-1", "", "2026-W47-2"]
)
def test_bad_dates_are_rejected(text: str) -> None:
    with pytest.raises(InvalidDateError):
        make("expense", date=text)


def test_date_spaces_are_trimmed() -> None:
    assert make("expense", date=" 2026-11-17 ").date == DAY


def test_unknown_kind_gives_readable_message() -> None:
    with pytest.raises(InvalidChoiceError) as info:
        make("refund")
    assert "income, expense, transfer" in info.value.message


def test_unknown_category_gives_readable_message() -> None:
    with pytest.raises(InvalidCategoryError) as info:
        make("expense", category="snacks")
    assert "'snacks'" in info.value.message and "food" in info.value.message


def test_from_input_rejects_transfer() -> None:
    with pytest.raises(InvalidTransferError, match="Ledger.transfer"):
        make("transfer")


# --- Row edge cases --------------------------------------------------------------


def test_missing_column_raises_data_import_error() -> None:
    row = dict(SAMPLES[1].to_row())
    del row["currency"]
    with pytest.raises(DataImportError, match="currency"):
        TransactionFactory.from_row(row)


def test_none_value_from_dictreader_counts_as_missing() -> None:
    row: dict[str, str | None] = dict(SAMPLES[1].to_row())
    row["direction"] = None
    with pytest.raises(DataImportError, match="direction"):
        TransactionFactory.from_row(row)


def test_id_and_non_eur_currency_survive_round_trip() -> None:
    original = Expense(
        id=987, account_id=4, amount=Money.of("19.99", "USD"), date=DAY, category=Category.FUN
    )
    rebuilt = TransactionFactory.from_row(original.to_row())
    assert rebuilt.id == 987
    assert rebuilt.amount == Money.of("19.99", "USD")


def test_transfer_columns_on_income_row_are_rejected() -> None:
    row = SAMPLES[0].to_row() | {"transfer_id": "tr-9", "direction": "out"}
    with pytest.raises(DataImportError, match="income"):
        TransactionFactory.from_row(row)


@pytest.mark.parametrize(
    "column,value,error",
    [
        ("kind", "refund", DataImportError),
        ("direction", "sideways", DataImportError),
        ("id", "abc", DataImportError),
        ("account_id", "1.5", DataImportError),
        ("amount", "12,50", InvalidAmountError),
        ("currency", "eur", InvalidCurrencyError),
        ("date", "17/11/2026", InvalidDateError),
    ],
)
def test_bad_row_values_raise_the_right_error(
    column: str, value: str, error: type[Exception]
) -> None:
    row = SAMPLES[2].to_row() | {column: value}
    with pytest.raises(error):
        TransactionFactory.from_row(row)


def test_row_columns_match_csv_columns() -> None:
    for sample in SAMPLES:
        assert tuple(sample.to_row()) == CSV_COLUMNS


# --- Registry --------------------------------------------------------------------


def test_registry_covers_every_kind() -> None:
    assert set(TransactionFactory._CLASSES) == set(Kind)
    assert set(TransactionFactory._ROW_EXTRAS) == set(Kind)
    for kind in Kind:
        assert TransactionFactory.from_row(_row_for(kind)).kind is kind


def _row_for(kind: Kind) -> dict[str, str]:
    return next(s.to_row() for s in SAMPLES if s.kind is kind)


def test_non_text_amount_is_rejected() -> None:
    with pytest.raises(InvalidAmountError, match="text"):
        TransactionFactory.from_input("expense", 12.5, "food", "2026-11-17", 1, transaction_id=7)  # type: ignore[arg-type]
