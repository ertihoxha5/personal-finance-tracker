"""Repository tests (#18): the same behaviour for CSV, JSON and SQLite, plus crash safety."""

import datetime as dt
import os
import sqlite3
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest

from pft.domain.category import AccountType, Category, Direction
from pft.domain.exceptions import DataImportError, StorageError
from pft.domain.money import Money
from pft.domain.transaction import Expense, Income, Transaction, Transfer
from pft.infrastructure import db
from pft.infrastructure.repository import (
    CsvRepository,
    JsonRepository,
    Repository,
    SqliteRepository,
    atomic_write,
)
from pft.services.ledger import Ledger

RepoFactory = Callable[[Path], Repository]

FACTORIES: dict[str, RepoFactory] = {
    "csv": lambda tmp: CsvRepository(tmp / "data"),
    "json": lambda tmp: JsonRepository(tmp / "data" / "tracker.json"),
    "sqlite": lambda tmp: SqliteRepository(tmp / "data" / "tracker.sqlite3"),
}


@pytest.fixture(params=list(FACTORIES))
def repo(request: pytest.FixtureRequest, tmp_path: Path) -> Repository:
    return FACTORIES[request.param](tmp_path)


def sample_ledger() -> Ledger:
    ledger = Ledger()
    bank = ledger.open_account("Bank", AccountType.BANK, Money.of("1000.50"))
    cash = ledger.open_account("Cash", AccountType.CASH, Money.of("-20.00"))
    ledger.add_transaction(
        bank.id,
        Income(
            id=1,
            account_id=bank.id,
            amount=Money.of("2200.00"),
            date=dt.date(2026, 11, 1),
            category=Category.SALARY,
            note="Salary, November",
        ),
    )
    ledger.add_transaction(
        bank.id,
        Expense(
            id=2,
            account_id=bank.id,
            amount=Money.of("64.50"),
            date=dt.date(2026, 11, 2),
            category=Category.FOOD,
            note='He said "hi"\nand left',
        ),
    )
    ledger.add_transaction(
        bank.id,
        Transfer(
            id=3,
            account_id=bank.id,
            amount=Money.of("50.00"),
            date=dt.date(2026, 11, 3),
            direction=Direction.OUT,
            transfer_id="t-1",
        ),
    )
    ledger.add_transaction(
        cash.id,
        Transfer(
            id=4,
            account_id=cash.id,
            amount=Money.of("50.00"),
            date=dt.date(2026, 11, 3),
            direction=Direction.IN,
            transfer_id="t-1",
        ),
    )
    return ledger


def snapshot(ledger: Ledger) -> tuple[object, ...]:
    accounts = [
        (a.id, a.name, a.type, a.opening_balance, a.balance, [t for t in a])
        for a in sorted(ledger.accounts, key=lambda a: a.id)
    ]
    return (accounts, ledger.net_worth, ledger.next_transaction_id())


def test_round_trip_gives_the_same_data(repo: Repository) -> None:
    original = sample_ledger()
    repo.save(original)
    assert snapshot(repo.load()) == snapshot(original)


def test_first_start_without_data_gives_empty_ledger(repo: Repository) -> None:
    ledger = repo.load()  # no data folder or file exists yet
    assert ledger.accounts == []
    assert ledger.net_worth == Money.zero()


def test_save_twice_keeps_one_copy_of_the_data(repo: Repository) -> None:
    ledger = sample_ledger()
    repo.save(ledger)
    repo.save(ledger)
    assert snapshot(repo.load()) == snapshot(ledger)


def test_saving_after_changes_replaces_old_data(repo: Repository) -> None:
    ledger = sample_ledger()
    repo.save(ledger)
    ledger.remove_transaction(1, 2)
    ledger.close_account(2)
    repo.save(ledger)
    loaded = repo.load()
    assert [a.id for a in loaded.accounts] == [1]
    assert 2 not in loaded.account(1)


def test_ids_stay_unique_after_reload(repo: Repository) -> None:
    repo.save(sample_ledger())
    loaded = repo.load()
    assert loaded.open_account("New", AccountType.CARD, Money.zero()).id == 3


def test_amounts_stay_exact(repo: Repository) -> None:
    ledger = Ledger()
    account = ledger.open_account("A", AccountType.BANK, Money.of("0.10"))
    ledger.add_transaction(
        account.id,
        Income(
            id=1,
            account_id=account.id,
            amount=Money.of("0.20"),
            date=dt.date(2026, 1, 1),
            category=Category.OTHER,
        ),
    )
    repo.save(ledger)
    assert str(repo.load().net_worth.amount) == "0.30"


def test_transaction_for_unknown_account_is_a_clear_import_error(
    repo: Repository, tmp_path: Path
) -> None:
    if isinstance(repo, SqliteRepository):
        pytest.skip("SQLite enforces this with a foreign key instead")
    repo.save(sample_ledger())
    if isinstance(repo, CsvRepository):
        path = repo.folder / "transactions.csv"
        path.write_text(path.read_text().replace(",1,income,", ",99,income,", 1))
    else:
        assert isinstance(repo, JsonRepository)
        text = repo.path.read_text().replace('"account_id": "1"', '"account_id": "99"', 1)
        repo.path.write_text(text)
    with pytest.raises(DataImportError, match="transaction 1"):
        repo.load()


# --- atomic_write ---------------------------------------------------------------------


def test_atomic_write_replaces_file_on_success(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    target.write_text("old")
    with atomic_write(target) as f:
        f.write("new")
    assert target.read_text() == "new"
    assert not target.with_suffix(".txt.tmp").exists()


def test_crash_while_writing_leaves_old_file_unchanged(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    target.write_text("old")
    with pytest.raises(RuntimeError), atomic_write(target) as f:
        f.write("half of the new con")
        raise RuntimeError("power cut")
    assert target.read_text() == "old"
    assert not target.with_suffix(".txt.tmp").exists()


def test_crash_during_replace_leaves_old_file_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "out.txt"
    target.write_text("old")

    def broken_replace(src: object, dst: object) -> None:
        raise OSError("disk vanished")

    monkeypatch.setattr(os, "replace", broken_replace)
    with pytest.raises(OSError), atomic_write(target) as f:
        f.write("new")
    assert target.read_text() == "old"
    assert not target.with_suffix(".txt.tmp").exists()


@pytest.mark.parametrize("kind", ["csv", "json"])
def test_failed_save_keeps_the_previously_saved_data(
    kind: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = FACTORIES[kind](tmp_path)
    original = sample_ledger()
    repo.save(original)

    def broken_replace(src: object, dst: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", broken_replace)
    changed = sample_ledger()
    changed.close_account(2)
    with pytest.raises(StorageError):
        repo.save(changed)
    monkeypatch.undo()
    assert snapshot(repo.load()) == snapshot(original)


def test_csv_creates_all_four_files_and_keeps_later_budget_data(tmp_path: Path) -> None:
    repo = CsvRepository(tmp_path / "data")
    repo.save(sample_ledger())
    names = {p.name for p in (tmp_path / "data").iterdir()}
    assert names == {"accounts.csv", "transactions.csv", "budgets.csv", "recurring.csv"}
    budgets = tmp_path / "data" / "budgets.csv"
    budgets.write_text("category,month,limit,currency\nfood,2026-11,300.00,EUR\n")
    repo.save(sample_ledger())
    assert "food,2026-11,300.00,EUR" in budgets.read_text()


def test_json_keeps_budgets_and_recurring_from_the_old_file(tmp_path: Path) -> None:
    repo = JsonRepository(tmp_path / "tracker.json")
    repo.save(sample_ledger())
    text = repo.path.read_text().replace('"budgets": []', '"budgets": [{"category": "food"}]')
    repo.path.write_text(text)
    repo.save(sample_ledger())
    assert '"category": "food"' in repo.path.read_text()


def test_corrupt_files_raise_import_errors(tmp_path: Path) -> None:
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not json")
    with pytest.raises(DataImportError):
        JsonRepository(bad_json).load()
    folder = tmp_path / "csv"
    folder.mkdir()
    (folder / "accounts.csv").write_text("id,name\n1,Bank\n")
    with pytest.raises(DataImportError, match="missing column"):
        CsvRepository(folder).load()


# --- SQLite specifics -------------------------------------------------------------------


def test_sqlite_failed_save_rolls_back_everything(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "t.sqlite3")
    original = sample_ledger()
    repo.save(original)

    broken = Ledger()
    broken.open_account("Same", AccountType.BANK, Money.zero())
    broken.open_account("Same", AccountType.BANK, Money.zero())  # name is UNIQUE in SQLite
    with pytest.raises(StorageError):
        repo.save(broken)
    assert snapshot(repo.load()) == snapshot(original)


def test_sqlite_refuses_to_round_a_sub_cent_amount(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "t.sqlite3")
    ledger = Ledger()
    ledger.open_account("A", AccountType.BANK, Money.of("1.00"))
    repo.save(ledger)
    # Money normally prevents sub-cent values, so force one to test the repository guard.
    object.__setattr__(ledger.accounts[0].opening_balance, "amount", Decimal("1.005"))
    with pytest.raises(StorageError, match="decimal places"):
        repo.save(ledger)
    assert repo.load().net_worth == Money.of("1.00")


def test_sqlite_stores_integer_cents(tmp_path: Path) -> None:
    path = tmp_path / "t.sqlite3"
    SqliteRepository(path).save(sample_ledger())
    conn = sqlite3.connect(path)
    types = {r[0] for r in conn.execute("SELECT typeof(amount_cents) FROM transactions")}
    types |= {r[0] for r in conn.execute("SELECT typeof(opening_balance_cents) FROM accounts")}
    conn.close()
    assert types == {"integer"}


def test_sqlite_upgrades_a_task_5_database_without_losing_rows(tmp_path: Path) -> None:
    path = tmp_path / "old.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
            opening_balance_cents INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE transactions (id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL REFERENCES accounts(id), occurred_on TEXT NOT NULL,
            description TEXT NOT NULL, amount_cents INTEGER NOT NULL);
        INSERT INTO accounts (name, opening_balance_cents) VALUES ('Checking', 150000);
        INSERT INTO transactions (account_id, occurred_on, description, amount_cents)
            VALUES (1, '2026-11-01', 'Salary', 220000), (1, '2026-11-02', 'Groceries', -6450);
        """
    )
    conn.close()

    ledger = SqliteRepository(path).load()

    assert ledger.net_worth == Money.of("3635.50")  # 1500 + 2200 - 64.50
    assert [t.note for t in ledger.account(1) if isinstance(t, Transaction)] == [
        "Salary",
        "Groceries",
    ]


def test_sqlite_load_does_not_create_a_database(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite3"
    SqliteRepository(path).load()
    assert not path.exists()


def test_seeded_demo_database_loads_into_a_ledger(tmp_path: Path) -> None:
    path = tmp_path / "demo.sqlite3"
    db.init_db(path, seed=True)
    ledger = SqliteRepository(path).load()
    assert {a.name for a in ledger.accounts} == {"Checking", "Savings"}
    assert ledger.net_worth == Money.of("8035.50")  # 1500 + 5000 + 2200 - 64.50 - 600
