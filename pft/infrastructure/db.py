"""SQLite connection and schema setup.

All money amounts are stored as integer cents to avoid floating-point rounding.
The full persistence layer (repositories, migrations) is owned by task #18;
this module only provides the database location, a connection helper and an
idempotent schema initialiser.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "tracker.sqlite3"
DB_PATH_ENV = "PFT_DB_PATH"

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    opening_balance_cents INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    occurred_on TEXT NOT NULL,
    description TEXT NOT NULL,
    amount_cents INTEGER NOT NULL
);
"""

SEED_ACCOUNTS = [("Checking", 150_000), ("Savings", 500_000)]
SEED_TRANSACTIONS = [
    ("Checking", "2026-11-01", "Salary", 220_000),
    ("Checking", "2026-11-02", "Groceries", -6_450),
    ("Checking", "2026-11-03", "Rent", -60_000),
]


def get_db_path() -> Path:
    """Return the database path, honouring the PFT_DB_PATH override."""
    override = os.environ.get(DB_PATH_ENV)
    return Path(override) if override else DEFAULT_DB_PATH


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open a connection, creating the parent directory if needed."""
    db_path = path if path is not None else get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path | None = None, *, seed: bool = False) -> Path:
    """Create the schema if missing and optionally insert demo data.

    Safe to run repeatedly: tables use IF NOT EXISTS and seeding is skipped
    when any account already exists.
    """
    db_path = path if path is not None else get_db_path()
    conn = connect(db_path)
    try:
        with conn:
            conn.executescript(SCHEMA)
            if seed:
                _seed(conn)
    finally:
        conn.close()
    return db_path


def _seed(conn: sqlite3.Connection) -> None:
    (count,) = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()
    if count:
        return
    conn.executemany(
        "INSERT INTO accounts (name, opening_balance_cents) VALUES (?, ?)",
        SEED_ACCOUNTS,
    )
    conn.executemany(
        "INSERT INTO transactions (account_id, occurred_on, description, amount_cents) "
        "SELECT id, ?, ?, ? FROM accounts WHERE name = ?",
        [(day, desc, cents, account) for account, day, desc, cents in SEED_TRANSACTIONS],
    )
