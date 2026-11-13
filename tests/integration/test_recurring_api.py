"""Recurring rules through the API and every repository (#25). Synthetic seed: Checking
3035.50 (ID 1), Savings 5000.00 (ID 2). "Today" is fixed at 15 November 2026."""

import datetime as dt
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from pft.api.main import app
from pft.api.store import LedgerStore, get_store
from pft.domain.category import AccountType, Category, Frequency
from pft.domain.money import Money
from pft.domain.recurring import RecurringTransaction
from pft.domain.transaction import Expense
from pft.infrastructure import db
from pft.infrastructure.repository import (
    CsvRepository,
    JsonRepository,
    Repository,
    SqliteRepository,
)
from pft.services.ledger import Ledger

TODAY = dt.date(2026, 11, 15)
RENT = {
    "kind": "expense",
    "account_id": 1,
    "amount": "600.00",
    "category": "rent",
    "note": "Flat rent",
    "frequency": "monthly",
    "start_date": "2026-09-01",
}


@pytest.fixture
def db_path(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / "recurring.sqlite3"
    db.init_db(path, seed=True)
    yield path
    app.dependency_overrides.clear()


def client_for(path: Path, today: dt.date = TODAY) -> TestClient:
    """A brand-new store on the same file, like a backend (re)started on ``today``."""
    store = LedgerStore(SqliteRepository(path), today=lambda: today)
    app.dependency_overrides[get_store] = lambda: store
    return TestClient(app)


def rent_rows(client: TestClient) -> list[str]:
    rows = client.get("/api/transactions", params={"category": "rent"}).json()
    return [r["date"] for r in rows if r["note"] == "Flat rent"]


def test_monthly_rent_from_1_september_adds_exactly_three(db_path: Path) -> None:
    client = client_for(db_path)
    response = client.post("/api/recurring", json=RENT)
    assert response.status_code == 201, response.text
    body = response.json()
    assert [t["date"] for t in body["added"]] == ["2026-09-01", "2026-10-01", "2026-11-01"]
    assert body["rule"]["last_run"] == "2026-11-01"
    assert body["rule"]["upcoming"] == ["2026-12-01", "2027-01-01", "2027-02-01"]
    assert rent_rows(client) == ["2026-09-01", "2026-10-01", "2026-11-01"]


def test_repeated_loads_and_a_restart_add_no_duplicates(db_path: Path) -> None:
    client_for(db_path).post("/api/recurring", json=RENT)
    for _ in range(3):
        client = client_for(db_path)  # a fresh store each time, as after a restart
        client.get("/api/accounts")
        client.get("/api/dashboard")
    assert rent_rows(client) == ["2026-09-01", "2026-10-01", "2026-11-01"]
    accounts = {a["name"]: a["balance"] for a in client.get("/api/accounts").json()}
    assert accounts["Checking"] == "1235.50"  # 3035.50 - 3 x 600


def test_a_later_day_adds_only_the_new_occurrence(db_path: Path) -> None:
    client_for(db_path).post("/api/recurring", json=RENT)
    later = client_for(db_path, today=dt.date(2026, 12, 2))
    assert rent_rows(later) == ["2026-09-01", "2026-10-01", "2026-11-01", "2026-12-01"]
    assert later.get("/api/recurring").json()[0]["last_run"] == "2026-12-01"


def test_end_date_is_respected(db_path: Path) -> None:
    client_for(db_path).post("/api/recurring", json={**RENT, "end_date": "2026-10-15"})
    later = client_for(db_path, today=dt.date(2027, 3, 1))
    assert rent_rows(later) == ["2026-09-01", "2026-10-01"]
    assert later.get("/api/recurring").json()[0]["upcoming"] == []


def test_month_end_rule_is_not_shifted_by_saving_and_reloading(db_path: Path) -> None:
    rule = {**RENT, "start_date": "2027-01-31"}
    client_for(db_path).post("/api/recurring", json=rule)
    for today in (dt.date(2027, 2, 28), dt.date(2027, 3, 31), dt.date(2027, 4, 30)):
        client = client_for(db_path, today=today)
        client.get("/api/accounts")
    assert rent_rows(client) == ["2027-01-31", "2027-02-28", "2027-03-31", "2027-04-30"]


def test_preview_lists_due_and_upcoming_without_saving(db_path: Path) -> None:
    client = client_for(db_path)
    params = {"frequency": "monthly", "start_date": "2026-08-31", "count": 4}
    body = client.get("/api/recurring/preview", params=params).json()
    assert body == {
        "due_count": 3,
        "due_now": ["2026-08-31", "2026-09-30", "2026-10-31"],
        "upcoming": ["2026-11-30", "2026-12-31", "2027-01-31", "2027-02-28"],
    }
    assert client.get("/api/recurring/preview", params=params).json() == body
    assert client.get("/api/recurring").json() == []


@pytest.mark.parametrize(
    ("change", "code", "field"),
    [
        ({"frequency": "daily"}, "invalid_choice", "frequency"),
        ({"start_date": "1/9/2026"}, "invalid_date", "start_date"),
        ({"end_date": "2026-08-01"}, "invalid_date", "end_date"),
        ({"amount": "0"}, "invalid_amount", None),
        ({"kind": "transfer"}, "invalid_transfer", "kind"),
    ],
)
def test_bad_rules_use_the_error_shape_and_save_nothing(
    db_path: Path, change: dict[str, str], code: str, field: str | None
) -> None:
    client = client_for(db_path)
    response = client.post("/api/recurring", json={**RENT, **change})
    assert response.status_code == 422
    assert response.json()["code"] == code
    if field is not None:
        assert response.json()["field"] == field
    assert client.get("/api/recurring").json() == []
    assert rent_rows(client) == []


def test_unknown_account_is_404(db_path: Path) -> None:
    assert (
        client_for(db_path).post("/api/recurring", json={**RENT, "account_id": 99}).status_code
        == 404
    )


def test_closing_the_account_removes_its_rules(db_path: Path) -> None:
    client = client_for(db_path)
    created = client.post(
        "/api/accounts", json={"name": "Wallet", "type": "cash", "opening_balance": "50.00"}
    )
    wallet = created.json()["id"]
    client.post("/api/recurring", json={**RENT, "account_id": wallet, "amount": "1.00"})
    assert client.delete(f"/api/accounts/{wallet}").status_code == 200
    assert client.get("/api/recurring").json() == []


# --- each repository keeps rules and last_run -------------------------------------------


def _ledger_with_rule() -> Ledger:
    ledger = Ledger()
    ledger.open_account("Checking", AccountType.BANK, Money.of("2000.00"))
    template = Expense(
        id=0,
        account_id=1,
        amount=Money.of("9.99"),
        date=dt.date(2027, 1, 31),
        category=Category.FUN,
    )
    rule = RecurringTransaction(
        template=template, frequency=Frequency.MONTHLY, start=dt.date(2027, 1, 31)
    )
    ledger.add_recurring(rule)
    ledger.apply_recurring(dt.date(2027, 3, 1))
    return ledger


REPOSITORIES: dict[str, Callable[[Path], Repository]] = {
    "csv": lambda p: CsvRepository(p / "csv"),
    "json": lambda p: JsonRepository(p / "pft.json"),
    "sqlite": lambda p: SqliteRepository(p / "pft.sqlite3"),
}


@pytest.mark.parametrize("name", list(REPOSITORIES))
def test_repository_round_trip_keeps_rules_and_last_run(name: str, tmp_path: Path) -> None:
    repo = REPOSITORIES[name](tmp_path)
    repo.save(_ledger_with_rule())
    loaded = repo.load()
    [rule] = loaded.recurring
    assert rule.last_run == dt.date(2027, 2, 28)
    assert rule.to_row() == _ledger_with_rule().recurring[0].to_row()
    assert loaded.apply_recurring(dt.date(2027, 3, 1)) == []
    added: list[Any] = loaded.apply_recurring(dt.date(2027, 3, 31))
    assert [t.date for t in added] == [dt.date(2027, 3, 31)]
