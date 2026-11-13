"""Task #24 formula guards use formatter registration, not exporter changes."""

import csv
import json
from pathlib import Path

import pytest

from pft.domain.money import Money
from pft.infrastructure.exporters import CsvExporter, JsonExporter, MarkdownExporter, format_value


@pytest.mark.parametrize("text", ["=SUM(A1)", "+SUM(A1)", "-SUM(A1)", "@SUM(A1)"])
def test_csv_formula_text_gets_one_leading_apostrophe(tmp_path: Path, text: str) -> None:
    path = tmp_path / "guard.csv"
    CsvExporter().export([{"note": text}], path)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        assert list(csv.DictReader(stream)) == [{"note": "'" + text}]


@pytest.mark.parametrize("text", ["", "Lunch with team", "'=SUM(A1)", "A=B", "Caf\u00e9"])
def test_ordinary_or_already_guarded_text_is_unchanged(text: str) -> None:
    assert format_value(text) == text


def test_guard_applies_to_numeric_text_but_preserves_typed_numbers(tmp_path: Path) -> None:
    path = tmp_path / "numbers.csv"
    CsvExporter().export(
        [
            {
                "text": "-12.50",
                "money": Money.of("-12.50"),
                "integer": -12,
            }
        ],
        path,
    )
    with path.open(encoding="utf-8-sig", newline="") as stream:
        assert list(csv.DictReader(stream)) == [
            {"text": "'-12.50", "money": "-12.50", "integer": "-12"}
        ]


def test_json_and_markdown_keep_formula_text_literal(tmp_path: Path) -> None:
    rows = [{"note": "=SUM(A1)", "amount": Money.of("-12.50")}]
    json_path = tmp_path / "literal.json"
    JsonExporter().export(rows, json_path)
    assert json.loads(json_path.read_text(encoding="utf-8")) == [
        {"note": "=SUM(A1)", "amount": "-12.50"}
    ]
    md_path = tmp_path / "literal.md"
    MarkdownExporter().export(rows, md_path)
    assert md_path.read_text(encoding="utf-8").splitlines()[-1] == "| =SUM(A1) | -12.50 |"
