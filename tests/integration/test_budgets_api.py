"""Budgets through the API, the CLI and every repository (#27). Synthetic seed: Checking
(ID 1) already has a 64.50 food expense on 2 November 2026. "Today" is 15 November 2026."""

import datetime as dt
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from pft.api.main import app
from pft.api.store import LedgerStore, get_store
from pft.cli import main
from pft.domain.budget import Budget
from pft.domain.category import AccountType, Category
from pft.domain.money import Money
from pft.infrastructure import db
from pft.infrastructure.repository import (
    CsvRepository,
    JsonRepository,
    Repository,
    SqliteRepository,
)
from pft.services.ledger import Ledger

TODAY = dt.date(2026, 11, 15)
FOOD = {"category": "food", "month": "2026-11", "limit": "200.00"}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    path = tmp_path / "budgets.sqlite3"
    db.init_db(path, seed=True)
    store = LedgerStore(SqliteRepository(path), today=lambda: TODAY)
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def spend(client: TestClient, amount: str, **change: Any) -> dict[str, Any]:
    body = {
        "kind": "expense",
        "account_id": 1,
        "amount": amount,
        "date": "2026-11-10",
        "category": "food",
    }
    response = client.post("/api/transactions", json={**body, **change})
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def food(client: TestClient) -> dict[str, Any]:
    [budget] = client.get("/api/budgets", params={"month": "2026-11"}).json()["budgets"]
    result: dict[str, Any] = budget
    return result


def test_set_budget_and_read_usage_from_the_server(client: TestClient) -> None:
    response = client.put("/api/budgets", json=FOOD)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "category": "food",
        "month": "2026-11",
        "limit": "200.00",
        "currency": "EUR",
        "spent": "64.50",
        "remaining": "135.50",
        "usage_percent": "32.2",
        "status": "ok",
        "level": None,
    }
    body = client.get("/api/budgets").json()  # default month is today's
    assert body["month"] == "2026-11"
    assert body["thresholds"] == {"warning": 80, "exceeded": 100}
    assert body["budgets"] == [response.json()]
    assert body["warnings"] == []


def test_plan_scenario_through_the_api(client: TestClient) -> None:
    client.put("/api/budgets", json=FOOD)
    assert spend(client, "85.50")["warnings"] == []  # 150.00 spent, 75%
    created = spend(client, "15.00")
    assert [w["message"] for w in created["warnings"]] == ["FOOD budget at 82%"]
    assert created["warnings"][0]["level"] == 80
    # Usage updates after spending, and the state is still visible on a later load.
    assert food(client) | {"spent": "165.00", "usage_percent": "82.5", "status": "warning"} == (
        food(client)
    )
    listed = client.get("/api/budgets", params={"month": "2026-11"}).json()
    assert [w["message"] for w in listed["warnings"]] == ["FOOD budget at 82%"]


def test_a_second_expense_above_80_does_not_repeat_and_100_is_new(client: TestClient) -> None:
    client.put("/api/budgets", json=FOOD)
    spend(client, "100.50")  # 165.00
    assert spend(client, "5.00")["warnings"] == []  # each request has a brand-new monitor
    exceeded = spend(client, "40.00")["warnings"]
    assert [(w["level"], w["message"]) for w in exceeded] == [(100, "FOOD budget at 105%")]
    assert food(client)["status"] == "exceeded"
    assert food(client)["remaining"] == "-10.00"


def test_income_and_other_categories_never_warn(client: TestClient) -> None:
    client.put("/api/budgets", json={**FOOD, "limit": "65.00"})
    assert spend(client, "900.00", kind="income")["warnings"] == []
    assert spend(client, "900.00", category="rent")["warnings"] == []
    assert spend(client, "900.00", date="2026-12-01")["warnings"] == []


def test_put_replaces_the_limit_and_delete_removes_it(client: TestClient) -> None:
    client.put("/api/budgets", json=FOOD)
    client.put("/api/budgets", json={**FOOD, "limit": "64.50"})
    assert food(client)["limit"] == "64.50"
    assert food(client)["status"] == "exceeded"  # exactly 100%
    assert client.delete("/api/budgets/2026-11/food").status_code == 200
    assert client.get("/api/budgets").json()["budgets"] == []
    missing = client.delete("/api/budgets/2026-11/food")
    assert missing.status_code == 422 and missing.json()["code"] == "budget_error"


def test_budgets_are_listed_per_month(client: TestClient) -> None:
    client.put("/api/budgets", json=FOOD)
    client.put("/api/budgets", json={"category": "rent", "month": "2026-12", "limit": "600"})
    december = client.get("/api/budgets", params={"month": "2026-12"}).json()
    assert [b["category"] for b in december["budgets"]] == ["rent"]
    assert december["budgets"][0]["usage_percent"] == "0.0"


@pytest.mark.parametrize(
    ("change", "code", "field"),
    [
        ({"limit": "0"}, "budget_error", "limit"),
        ({"limit": "abc"}, "invalid_amount", "limit"),
        ({"month": "2026-13"}, "budget_error", "month"),
        ({"category": "holidays"}, "invalid_category", "category"),
    ],
)
def test_bad_budgets_use_the_error_shape_and_save_nothing(
    client: TestClient, change: dict[str, str], code: str, field: str
) -> None:
    response = client.put("/api/budgets", json={**FOOD, **change})
    assert response.status_code == 422
    assert (response.json()["code"], response.json()["field"]) == (code, field)
    assert client.get("/api/budgets").json()["budgets"] == []


def test_a_bad_month_in_the_query_is_reported(client: TestClient) -> None:
    response = client.get("/api/budgets", params={"month": "11/2026"})
    assert response.status_code == 422 and response.json()["field"] == "month"


def test_saving_the_ledger_keeps_the_budgets(client: TestClient) -> None:
    client.put("/api/budgets", json=FOOD)
    spend(client, "1.00")
    client.post("/api/accounts", json={"name": "Wallet", "type": "cash", "opening_balance": "5"})
    assert food(client)["limit"] == "200.00"


# --- each repository keeps budgets apart from the Ledger ---------------------------------

REPOSITORIES: dict[str, Callable[[Path], Repository]] = {
    "csv": lambda p: CsvRepository(p / "csv"),
    "json": lambda p: JsonRepository(p / "pft.json"),
    "sqlite": lambda p: SqliteRepository(p / "pft.sqlite3"),
}


@pytest.mark.parametrize("name", list(REPOSITORIES))
def test_repository_round_trip_keeps_budgets(name: str, tmp_path: Path) -> None:
    repo = REPOSITORIES[name](tmp_path)
    assert repo.load_budgets() == []
    budgets = [
        Budget(Category.FOOD, "2026-11", Money.of("200.00")),
        Budget(Category.RENT, "2026-11", Money.of("600.00")),
    ]
    ledger = Ledger()
    ledger.open_account("Checking", AccountType.BANK, Money.of("100.00"))
    repo.save(ledger)
    repo.save_budgets(budgets)
    repo.save(ledger)  # saving the Ledger again must not lose the budgets
    assert repo.load_budgets() == budgets
    assert [a.name for a in repo.load().accounts] == ["Checking"]
    repo.save_budgets(budgets[:1])
    assert repo.load_budgets() == budgets[:1]


@pytest.mark.parametrize("name", list(REPOSITORIES))
def test_budgets_can_be_saved_before_any_ledger(name: str, tmp_path: Path) -> None:
    repo = REPOSITORIES[name](tmp_path)
    repo.save_budgets([Budget(Category.FUN, "2026-12", Money.of("50.00"))])
    assert [b.category for b in repo.load_budgets()] == [Category.FUN]
    assert repo.load().accounts == []


# --- the CLI prints the warnings -------------------------------------------------------------


def test_cli_prints_the_warning_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(db.DB_PATH_ENV, str(tmp_path / "cli.sqlite3"))

    def run(*argv: str) -> str:
        assert main(list(argv)) == 0
        return capsys.readouterr().out

    run("account", "add", "Bank", "--opening", "1000")
    assert "Budget set: food 2026-11, limit 200.00 EUR" in run(
        "budget", "set", "FOOD", "200", "--month", "2026-11"
    )
    add = ("add", "expense")
    assert "Warning" not in run(*add, "150", "food", "--date", "2026-11-10")
    assert "Warning: FOOD budget at 82%" in run(*add, "15", "food", "--date", "2026-11-11")
    assert "Warning" not in run(*add, "5", "food", "--date", "2026-11-12")
    assert "Warning" not in run("add", "income", "900", "food", "--date", "2026-11-12")
    assert "Warning: FOOD budget at 100%" in run(*add, "30", "food", "--date", "2026-11-13")
    listing = run("budget", "list", "--month", "2026-11")
    assert "200.00 EUR" in listing and "100%" in listing and "exceeded" in listing
    assert "No budgets for 2026-10" in run("budget", "list", "--month", "2026-10")


def test_cli_rejects_a_bad_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(db.DB_PATH_ENV, str(tmp_path / "cli.sqlite3"))
    assert main(["budget", "set", "food", "0"]) == 1
    assert "more than zero" in capsys.readouterr().err
