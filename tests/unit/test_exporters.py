"""Task #16 export contracts and CSV file behavior."""

import csv
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from pft.domain.category import Category, Kind
from pft.domain.money import Money
from pft.domain.transaction import CSV_COLUMNS, Expense
from pft.infrastructure.exporters import CsvExporter, Exporter, ExportRow, format_value


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def test_csv_exporter_is_registered_and_format_lookup_ignores_case() -> None:
    assert Exporter.registry["csv"] is CsvExporter
    assert isinstance(Exporter.for_format("csv"), CsvExporter)
    assert isinstance(Exporter.for_format(" CSV "), CsvExporter)


def test_unknown_format_lists_registered_formats() -> None:
    with pytest.raises(ValueError, match="unknown export format 'xml'; known formats: csv"):
        Exporter.for_format("xml")


def test_base_exporter_is_abstract() -> None:
    with pytest.raises(TypeError):
        Exporter()  # type: ignore[abstract]


@pytest.mark.parametrize(
    "value, expected",
    [
        (Money.of("12.5"), "12.50"),
        (Money.of("-0.10"), "-0.10"),
        (date(2026, 11, 12), "2026-11-12"),
        (Category.FOOD, "FOOD"),
        (Kind.EXPENSE, "EXPENSE"),
        (None, ""),
        (42, "42"),
        ("Café", "Café"),
    ],
)
def test_format_value_dispatch(value: object, expected: str) -> None:
    assert format_value(value) == expected


def test_csv_quotes_special_characters_and_preserves_unicode(tmp_path: Path) -> None:
    path = tmp_path / "transactions.csv"
    rows = [
        {
            "note": 'Café, "lunch"\nsecond line',
            "amount": Money.of("12.50"),
            "date": date(2026, 11, 12),
        }
    ]
    Exporter.for_format("csv").export(iter(rows), path)
    columns, exported = read_csv(path)
    assert columns == ["note", "amount", "date"]
    assert exported == [
        {"note": 'Café, "lunch"\nsecond line', "amount": "12.50", "date": "2026-11-12"}
    ]
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in raw


def test_real_transaction_rows_keep_the_existing_csv_contract(tmp_path: Path) -> None:
    item = Expense(
        id=1,
        account_id=2,
        amount=Money.of("12.50"),
        date=date(2026, 11, 12),
        category=Category.FOOD,
        note="Lunch with team",
    )
    path = tmp_path / "transaction.csv"
    CsvExporter().export((transaction.to_row() for transaction in [item]), path)
    columns, rows = read_csv(path)
    assert columns == list(CSV_COLUMNS)
    assert rows == [item.to_row()]
    assert rows[0]["category"] == "food"


def test_empty_transaction_export_still_has_a_header(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    CsvExporter().export([], path)
    assert read_csv(path) == (list(CSV_COLUMNS), [])


def test_report_schema_supports_empty_and_populated_exports(tmp_path: Path) -> None:
    path = tmp_path / "report.csv"
    exporter = CsvExporter(fieldnames=("category", "spent"))
    exporter.export([], path)
    assert read_csv(path) == (["category", "spent"], [])
    exporter.export([{"spent": Money.of("12.50"), "category": Category.FOOD}], path)
    assert read_csv(path) == (["category", "spent"], [{"category": "FOOD", "spent": "12.50"}])


def test_failed_row_preserves_existing_file_and_cleans_temporary_file(tmp_path: Path) -> None:
    path = tmp_path / "existing.csv"
    path.write_text("previous export", encoding="utf-8")
    with pytest.raises(ValueError, match="fields not in fieldnames"):
        CsvExporter().export([{"note": "first"}, {"note": "second", "extra": "unexpected"}], path)
    assert path.read_text(encoding="utf-8") == "previous export"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["existing.csv"]


def test_generator_failure_does_not_leave_partial_export(tmp_path: Path) -> None:
    def broken_rows() -> Iterator[ExportRow]:
        yield {"note": "first"}
        raise RuntimeError("source failed")

    path = tmp_path / "failed.csv"
    with pytest.raises(RuntimeError, match="source failed"):
        CsvExporter().export(broken_rows(), path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("columns", [(), ("note", "note")])
def test_invalid_columns_fail_before_creating_file(
    tmp_path: Path, columns: tuple[str, ...]
) -> None:
    with pytest.raises(ValueError, match="nonempty and unique"):
        CsvExporter(fieldnames=columns).export([], tmp_path / "invalid.csv")
    assert list(tmp_path.iterdir()) == []
