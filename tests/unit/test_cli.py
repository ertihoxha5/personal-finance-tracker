from pathlib import Path

import pytest

from pft.__main__ import main
from pft.infrastructure import db


def test_init_command_creates_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "cli.sqlite3"
    monkeypatch.setenv(db.DB_PATH_ENV, str(path))
    assert main(["init", "--seed"]) == 0
    assert path.exists()
    assert str(path) in capsys.readouterr().out
