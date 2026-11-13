"""Task #24 format extensions preserve the existing exporter strategies."""

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from pft.domain.category import Category
from pft.domain.money import Money
from pft.domain.transaction import CSV_COLUMNS
from pft.infrastructure.exporters import Exporter, ExportRow, JsonExporter, MarkdownExporter


@pytest.mark.parametrize("name, expected", [("json", JsonExporter), ("md", MarkdownExporter)])
def test_new_formats_register_themselves(name: str, expected: type[Exporter]) -> None:
    assert isinstance(Exporter.for_format(name), expected)
    assert isinstance(Exporter.for_format(f" {name.upper()} "), expected)


def test_json_loads_and_preserves_exact_amounts_and_unicode(tmp_path: Path) -> None:
    path = tmp_path / "export.json"
    JsonExporter().export(
        iter(
            [
                {
                    "id": 7,
                    "amount": Money.of("123456789.01"),
                    "note": "Caf\u00e9",
                    "date": date(2026, 11, 13),
                    "category": Category.FOOD,
                    "optional": None,
                }
            ]
        ),
        path,
    )
    with path.open(encoding="utf-8") as stream:
        assert json.load(stream) == [
            {
                "id": 7,
                "amount": "123456789.01",
                "note": "Caf\u00e9",
                "date": "2026-11-13",
                "category": "FOOD",
                "optional": None,
            }
        ]
    assert '\n  {\n    "id": 7,' in path.read_text(encoding="utf-8")


def test_empty_json_is_a_valid_array(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    JsonExporter().export([], path)
    assert json.loads(path.read_text(encoding="utf-8")) == []


def test_markdown_table_formats_money_and_missing_cells(tmp_path: Path) -> None:
    path = tmp_path / "export.md"
    MarkdownExporter().export(
        [
            {"note": "Lunch", "amount": Money.of("12.50")},
            {"note": "Other"},
        ],
        path,
    )
    assert path.read_text(encoding="utf-8") == (
        "| note | amount |\n| --- | --- |\n| Lunch | 12.50 |\n| Other |  |\n"
    )


def test_markdown_escapes_table_delimiters_line_breaks_and_html(tmp_path: Path) -> None:
    path = tmp_path / "escaped.md"
    MarkdownExporter().export([{"note": "A|B\r\n<script>\\end"}], path)
    assert path.read_text(encoding="utf-8").splitlines()[-1] == (
        "| A\\|B<br>&lt;script&gt;\\\\end |"
    )


def test_empty_markdown_has_a_table_header(tmp_path: Path) -> None:
    path = tmp_path / "empty.md"
    MarkdownExporter().export([], path)
    assert path.read_text(encoding="utf-8").splitlines()[0] == (
        "| " + " | ".join(CSV_COLUMNS) + " |"
    )
    MarkdownExporter(fieldnames=["category", "spent"]).export([], path)
    assert path.read_text(encoding="utf-8") == "| category | spent |\n| --- | --- |\n"


@pytest.mark.parametrize("fmt", ["json", "md"])
def test_failed_source_preserves_previous_export(tmp_path: Path, fmt: str) -> None:
    def broken_rows() -> Iterator[ExportRow]:
        yield {"note": "first"}
        raise RuntimeError("source failed")

    path = tmp_path / f"export.{fmt}"
    path.write_text("previous", encoding="utf-8")
    with pytest.raises(RuntimeError, match="source failed"):
        Exporter.for_format(fmt).export(broken_rows(), path)
    assert path.read_text(encoding="utf-8") == "previous"
    assert list(tmp_path.iterdir()) == [path]


def test_markdown_rejects_extra_cells_before_replacing_file(tmp_path: Path) -> None:
    path = tmp_path / "export.md"
    path.write_text("previous", encoding="utf-8")
    with pytest.raises(ValueError, match="fields not in fieldnames"):
        MarkdownExporter().export([{"note": "first"}, {"extra": "second"}], path)
    assert path.read_text(encoding="utf-8") == "previous"
