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
