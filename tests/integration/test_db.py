from pathlib import Path

import pytest

from pft.infrastructure import db


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "nested" / "test.sqlite3"
    monkeypatch.setenv(db.DB_PATH_ENV, str(path))
    return path


def test_env_override_is_used(db_path: Path) -> None:
    assert db.get_db_path() == db_path
    assert db.init_db() == db_path
    assert db_path.exists()


def test_record_survives_reopen(db_path: Path) -> None:
    db.init_db()
    conn = db.connect()
    with conn:
        conn.execute(
            "INSERT INTO accounts (name, opening_balance_cents) VALUES (?, ?)",
            ("Wallet", 1_234),
        )
    conn.close()

    conn = db.connect()
    row = conn.execute(
        "SELECT name, opening_balance_cents FROM accounts WHERE name = 'Wallet'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert (row["name"], row["opening_balance_cents"]) == ("Wallet", 1_234)


def test_init_with_seed_is_idempotent(db_path: Path) -> None:
    db.init_db(seed=True)
    db.init_db(seed=True)
    conn = db.connect()
    (accounts,) = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()
    (txns,) = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()
    conn.close()
    assert accounts == len(db.SEED_ACCOUNTS)
    assert txns == len(db.SEED_TRANSACTIONS)


def test_amounts_are_integer_cents(db_path: Path) -> None:
    db.init_db(seed=True)
    conn = db.connect()
    types = {r[0] for r in conn.execute("SELECT typeof(amount_cents) FROM transactions")}
    conn.close()
    assert types == {"integer"}
