"""Task #32 CLI exports use the registry and synthetic SQLite records."""

import csv
import json
from collections.abc import Iterable
from pathlib import Path
from unittest.mock import patch

import pytest

from pft.cli import main
from pft.infrastructure import db
from pft.infrastructure.exporters import Exporter, ExportRow


@pytest.fixture
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "cli-exports.sqlite3"
    monkeypatch.setenv(db.DB_PATH_ENV, str(path))
    db.init_db(path, seed=True)
    return path


@pytest.mark.parametrize("fmt", ["csv", "json", "md"])
def test_each_registered_format_writes_file_and_prints_path(
    database: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], fmt: str
) -> None:
    output = tmp_path / f"transactions.{fmt}"
    assert main(["export", "transactions", "--format", fmt, "--out", str(output)]) == 0
    captured = capsys.readouterr()
    assert str(output.resolve()) in captured.out
    assert captured.err == ""
    assert output.stat().st_size > 0
    if fmt == "json":
        with output.open(encoding="utf-8") as stream:
            rows = json.load(stream)
        assert rows and all(isinstance(row["amount"], str) for row in rows)
    elif fmt == "csv":
        with output.open(encoding="utf-8-sig", newline="") as stream:
            assert list(csv.DictReader(stream))
    else:
        assert output.read_text(encoding="utf-8").splitlines()[1].startswith("| --- |")


def test_unknown_format_is_friendly_and_lists_registry(
    database: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "export.xml"
    assert main(["export", "transactions", "--format", "xml", "--out", str(output)]) == 1
    captured = capsys.readouterr()
    assert "unknown export format" in captured.err
    assert ", ".join(sorted(Exporter.registry)) in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""
    assert not output.exists()


def test_new_registry_strategy_works_without_cli_changes(
    database: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class TestExporter(Exporter):
        def export(self, rows: Iterable[ExportRow], path: str | Path) -> None:
            Path(path).write_text(str(len(list(rows))), encoding="utf-8")

    monkeypatch.setitem(Exporter.registry, "test-format", TestExporter)
    output = tmp_path / "custom.txt"
    assert main(["export", "transactions", "--format", "test-format", "--out", str(output)]) == 0
    assert int(output.read_text(encoding="utf-8")) > 0


def test_file_failure_is_reported_without_traceback(
    database: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "missing-folder" / "transactions.json"
    assert main(["export", "transactions", "--format", "json", "--out", str(output)]) == 1
    captured = capsys.readouterr()
    assert "Could not write export" in captured.err
    assert "Traceback" not in captured.err
    assert not output.exists()


def test_transaction_export_does_not_save_or_modify_repository(
    database: Path, tmp_path: Path
) -> None:
    with patch("pft.cli.SqliteRepository.save") as save:
        assert (
            main(
                ["export", "transactions", "--format", "json", "--out", str(tmp_path / "out.json")]
            )
            == 0
        )
    save.assert_not_called()


def test_empty_repository_still_creates_loadable_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(db.DB_PATH_ENV, str(tmp_path / "empty.sqlite3"))
    output = tmp_path / "empty.json"
    assert main(["export", "transactions", "--format", "json", "--out", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("fmt", ["csv", "json", "md"])
def test_monthly_export_supports_every_format(
    database: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], fmt: str
) -> None:
    output = tmp_path / f"monthly.{fmt}"
    assert main(["report", "monthly", "2026-11", "--export", fmt, "--out", str(output)]) == 0
    assert str(output.resolve()) in capsys.readouterr().out
    if fmt == "json":
        rows = json.loads(output.read_text(encoding="utf-8"))
        assert all(row["month"] == "2026-11" for row in rows)
        assert all(isinstance(row["value"], str) for row in rows)
        summary = {row["label"]: row["value"] for row in rows if row["section"] == "summary"}
        assert summary == {
            "income": "2200.00",
            "expenses": "664.50",
            "net": "1535.50",
            "savingsRate": "69.8",
        }
    elif fmt == "csv":
        with output.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert rows[0]["label"] == "income"
        assert all(row["month"] == "2026-11" for row in rows)
    else:
        assert "| month | section | label | value | unit |" in output.read_text(encoding="utf-8")


def test_monthly_export_uses_default_path_and_existing_month_option(
    database: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["report", "monthly", "--month", "2026-11", "--export", "json"]) == 0
    assert json.loads((tmp_path / "monthly-report-2026-11.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "args, message",
    [
        (["2026-11", "--month", "2026-10"], "disagree"),
        (["2026-11", "--out", "report.txt"], "requires --export"),
        (["2026-11", "--export", "unknown"], "known formats"),
        (["0000-01", "--export", "json"], "year"),
    ],
)
def test_monthly_export_errors_are_friendly(
    database: Path, capsys: pytest.CaptureFixture[str], args: list[str], message: str
) -> None:
    assert main(["report", "monthly", *args]) == 1
    captured = capsys.readouterr()
    assert message in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""


def test_empty_month_export_has_zero_summary_rows(database: Path, tmp_path: Path) -> None:
    output = tmp_path / "empty-month.json"
    assert main(["report", "monthly", "2020-01", "--export", "json", "--out", str(output)]) == 0
    rows = json.loads(output.read_text(encoding="utf-8"))
    assert len(rows) == 4
    assert [row["value"] for row in rows] == ["0.00", "0.00", "0.00", "0.0"]


def test_negative_monthly_net_remains_a_numeric_csv_value(database: Path, tmp_path: Path) -> None:
    assert main(["add", "expense", "40", "food", "--account", "1", "--date", "2020-01-15"]) == 0
    output = tmp_path / "negative.csv"
    assert main(["report", "monthly", "2020-01", "--export", "csv", "--out", str(output)]) == 0
    with output.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert next(row["value"] for row in rows if row["label"] == "net") == "-40.00"
