"""SQLite connection and schema setup.

All money amounts are stored as integer cents to avoid floating-point rounding.
This module provides the database location, a connection helper and an idempotent
schema initialiser that also upgrades a task-#5 database. Reading and writing domain
objects is SqliteRepository (pft/infrastructure/repository.py, task #18).
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
    opening_balance_cents INTEGER NOT NULL DEFAULT 0,
    type TEXT NOT NULL DEFAULT 'bank',
    currency TEXT NOT NULL DEFAULT 'EUR'
);

-- amount_cents is always positive; kind (and a transfer's direction) gives the sign.
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    kind TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    currency TEXT NOT NULL DEFAULT 'EUR',
    occurred_on TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'other',
    note TEXT NOT NULL DEFAULT '',
    transfer_id TEXT,
    direction TEXT
);

-- Recurring rules (#25): a template income/expense plus its schedule. last_run is the date
-- of the last occurrence already added, so a restart never adds it again.
CREATE TABLE IF NOT EXISTS recurring (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    kind TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    category TEXT NOT NULL DEFAULT 'other',
    note TEXT NOT NULL DEFAULT '',
    frequency TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT,
    last_run TEXT
);
"""

# Task #5 created accounts without type/currency and transactions with a signed amount and a
# description. This rebuilds the old transactions table in the #18 shape inside one
# transaction, keeping every row, so a failed upgrade leaves the old database as it was.
_UPGRADE_FROM_V1 = """
BEGIN;
ALTER TABLE accounts ADD COLUMN type TEXT NOT NULL DEFAULT 'bank';
ALTER TABLE accounts ADD COLUMN currency TEXT NOT NULL DEFAULT 'EUR';
ALTER TABLE transactions RENAME TO transactions_v1;
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    kind TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    currency TEXT NOT NULL DEFAULT 'EUR',
    occurred_on TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'other',
    note TEXT NOT NULL DEFAULT '',
    transfer_id TEXT,
    direction TEXT
);
INSERT INTO transactions (id, account_id, kind, amount_cents, occurred_on, note)
SELECT id, account_id, CASE WHEN amount_cents < 0 THEN 'expense' ELSE 'income' END,
       ABS(amount_cents), occurred_on, description
FROM transactions_v1 WHERE amount_cents != 0;
DROP TABLE transactions_v1;
COMMIT;
"""

# (account, type, opening balance in cents)
SEED_ACCOUNTS = [("Checking", "bank", 150_000), ("Savings", "savings", 500_000)]
# (account, date, kind, category, note, positive amount in cents)
SEED_TRANSACTIONS = [
    ("Checking", "2026-11-01", "income", "salary", "Salary", 220_000),
    ("Checking", "2026-11-02", "expense", "food", "Groceries", 6_450),
    ("Checking", "2026-11-03", "expense", "rent", "Rent", 60_000),
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
        _upgrade_if_old(conn)
        with conn:
            conn.executescript(SCHEMA)
            if seed:
                _seed(conn)
    finally:
        conn.close()
    return db_path


def _upgrade_if_old(conn: sqlite3.Connection) -> None:
    """Move a task-#5 database to the current shape; does nothing for a new or current one."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(transactions)")}
    if columns and "kind" not in columns:
        conn.executescript(_UPGRADE_FROM_V1)


def _seed(conn: sqlite3.Connection) -> None:
    (count,) = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()
    if count:
        return
    conn.executemany(
        "INSERT INTO accounts (name, type, opening_balance_cents) VALUES (?, ?, ?)",
        SEED_ACCOUNTS,
    )
    conn.executemany(
        "INSERT INTO transactions (account_id, occurred_on, kind, category, note, amount_cents) "
        "SELECT id, ?, ?, ?, ?, ? FROM accounts WHERE name = ?",
        [
            (day, kind, category, note, cents, account)
            for account, day, kind, category, note, cents in SEED_TRANSACTIONS
        ],
    )
