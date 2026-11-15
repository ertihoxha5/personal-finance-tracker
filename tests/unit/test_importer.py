"""Bank CSV import validates each row; previews never mutate the live Ledger."""

import io
from pathlib import Path
from unittest.mock import patch

import pytest

from pft.domain.category import AccountType, Kind
from pft.domain.exceptions import AccountNotFoundError, DataImportError
from pft.domain.money import Money
from pft.infrastructure.importer import BankCsvImporter
from pft.services.ledger import Ledger

HEADER = "date,amount,category,note\n"


@pytest.fixture
def ledger() -> Ledger:
    ledger = Ledger()
    ledger.open_account("Bank", AccountType.BANK, Money.of("100.00"))
    return ledger


def test_signed_amounts_import_income_and_expense_exactly(ledger: Ledger) -> None:
    result = BankCsvImporter().import_stream(
        ledger,
        io.StringIO(HEADER + "2026-11-15,-12.50,food,Lunch\n2026-11-16,100.10,salary,Pay\n"),
        1,
    )
    assert result.errors == ()
    assert [item.row_number for item in result.accepted] == [2, 3]
    assert [item.transaction.kind for item in result.accepted] == [Kind.EXPENSE, Kind.INCOME]
    assert ledger.account(1).balance == Money.of("187.60")


def test_valid_rows_are_kept_and_invalid_rows_have_number_reason_and_field(ledger: Ledger) -> None:
    result = BankCsvImporter().import_stream(
        ledger,
        io.StringIO(
            HEADER + "2026-11-15,-12.50,food,Lunch\n"
            "2026-02-30,12,food,Bad date\n2026-11-15,0,food,Zero\n"
            "2026-11-15,20,salary,Pay\n"
        ),
        1,
    )
    assert [item.row_number for item in result.accepted] == [2, 5]
    assert [item.transaction.id for item in result.accepted] == [1, 2]
    assert [issue.row_number for issue in result.errors] == [3, 4]
    assert [issue.field for issue in result.errors] == ["date", "amount"]
    assert all(issue.reason for issue in result.errors)
    assert ledger.account(1).balance == Money.of("107.50")


@pytest.mark.parametrize(
    "amount", ["0", "-0.00", "NaN", "Infinity", "1.234", "--12", "-+12", "1e2"]
)
def test_invalid_amount_is_rejected(ledger: Ledger, amount: str) -> None:
    result = BankCsvImporter().import_stream(
        ledger, io.StringIO(HEADER + f"2026-11-15,{amount},food,Test\n"), 1
    )
    assert not result.accepted
    assert result.errors[0].field == "amount"
    assert list(ledger.all_transactions()) == []


def test_decimal_comma_quotes_bom_unicode_and_multiline_note(
    ledger: Ledger, tmp_path: Path
) -> None:
    path = tmp_path / "bank.csv"
    path.write_text(
        HEADER + '2026-11-15,"-12,50",food,"Caf\u00e9, lunch\nwith team"\n',
        encoding="utf-8-sig",
        newline="",
    )
    result = BankCsvImporter().import_file(ledger, path, 1)
    assert result.errors == ()
    assert result.accepted[0].row_number == 3
    assert result.accepted[0].transaction.note == "Caf\u00e9, lunch\nwith team"
    assert result.accepted[0].transaction.amount == Money.of("12.50")


def test_preview_preserves_live_data_ids_and_observers(ledger: Ledger) -> None:
    class Observer:
        def update(self, event: object) -> None:
            pytest.fail("Preview must not notify live observers")

    ledger.subscribe(Observer())
    ledger.restore_id_counters(5, 42)
    result = BankCsvImporter().preview(
        ledger, io.StringIO(HEADER + "2026-11-15,-12.50,food,Lunch\n"), 1
    )
    assert result.accepted[0].transaction.id == 42
    assert list(ledger.all_transactions()) == []
    assert ledger.account(1).balance == Money.of("100.00")
    assert ledger.next_transaction_id() == 42
    assert ledger.next_account_id == 5


@pytest.mark.parametrize(
    "text",
    ["", "date,amount\n", "date,amount,category,amount\n", "date,amount,category,unexpected\n"],
)
def test_invalid_header_aborts_before_mutation(ledger: Ledger, text: str) -> None:
    with pytest.raises(DataImportError):
        BankCsvImporter().import_stream(ledger, io.StringIO(text), 1)
    assert list(ledger.all_transactions()) == []


def test_malformed_csv_after_valid_row_does_not_partially_import(ledger: Ledger) -> None:
    with pytest.raises(DataImportError, match="Invalid CSV"):
        BankCsvImporter().import_stream(
            ledger,
            io.StringIO(HEADER + '2026-11-15,10,salary,Pay\n2026-11-15,-12,food,"unclosed'),
            1,
        )
    assert list(ledger.all_transactions()) == []


def test_wrong_column_count_reports_issue_and_continues(ledger: Ledger) -> None:
    result = BankCsvImporter().import_stream(
        ledger,
        io.StringIO(
            HEADER + "2026-11-15,10\n2026-11-15,-12,food,Note,Extra\n2026-11-15,+5,salary,Pay\n"
        ),
        1,
    )
    assert [issue.row_number for issue in result.errors] == [2, 3]
    assert [item.row_number for item in result.accepted] == [4]


def test_currency_mismatch_rejects_only_that_row(ledger: Ledger) -> None:
    result = BankCsvImporter().import_stream(
        ledger,
        io.StringIO(
            "date,amount,category,currency\n2026-11-15,10,salary,USD\n2026-11-15,5,salary,EUR\n"
        ),
        1,
    )
    assert len(result.errors) == 1
    assert len(result.accepted) == 1
    assert ledger.account(1).balance == Money.of("105.00")


def test_unknown_category_is_a_numbered_error(ledger: Ledger) -> None:
    result = BankCsvImporter().import_stream(
        ledger, io.StringIO("date,amount,category\n2026-11-15,-10,not-a-category\n"), 1
    )
    assert result.errors[0].row_number == 2
    assert result.errors[0].field == "category"


def test_row_limit_aborts_before_mutation(ledger: Ledger) -> None:
    with (
        patch("pft.infrastructure.importer.MAX_IMPORT_ROWS", 1),
        pytest.raises(DataImportError, match="row limit"),
    ):
        BankCsvImporter().import_stream(
            ledger, io.StringIO(HEADER + "2026-11-15,5,salary,Pay\n2026-11-15,6,salary,Pay\n"), 1
        )
    assert list(ledger.all_transactions()) == []


def test_header_only_and_blank_rows_are_empty_imports(ledger: Ledger) -> None:
    result = BankCsvImporter().import_stream(ledger, io.StringIO(HEADER + "\n,,,\n"), 1)
    assert result.accepted == ()
    assert result.errors == ()


def test_unknown_account_is_not_silently_created(ledger: Ledger) -> None:
    with pytest.raises(AccountNotFoundError):
        BankCsvImporter().import_stream(ledger, io.StringIO(HEADER), 999)
