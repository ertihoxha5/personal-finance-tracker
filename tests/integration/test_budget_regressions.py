"""Regression tests for the two #27 review findings.

1. Warning history is stored: deleting the expense that crossed a threshold and adding it
   again must not send the same warning a second time that month. Before the fix every API
   request (and every CLI run) built a new monitor with an empty memory.
2. A budget accepts exactly the months the report API accepts: ``0000-01`` used to be saved
   as a budget, and its report then answered 422.

Synthetic seed: Checking (ID 1) has a 64.50 food expense on 2 November 2026. "Today" is
15 November 2026.
"""

import datetime as dt
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import pft.services.reports as reports
from pft.api.main import app
from pft.api.store import LedgerStore, get_store
from pft.cli import main
from pft.domain import budget as budget_module
from pft.domain.budget import (
    BUDGET_EXCEEDED,
    BUDGET_WARNING,
    MAX_YEAR,
    MIN_YEAR,
    Budget,
    SentWarning,
)
from pft.domain.category import AccountType, Category
from pft.domain.exceptions import BudgetError, DataImportError, InvalidDateError
from pft.domain.money import Money
from pft.domain.transaction import Expense
from pft.infrastructure import db
from pft.infrastructure.repository import (
    CsvRepository,
    JsonRepository,
    Repository,
    SqliteRepository,
)
from pft.services.budget_monitor import BudgetMonitor, BudgetWarning, forget_changed
from pft.services.ledger import Ledger

TODAY = dt.date(2026, 11, 15)
NOVEMBER = "2026-11"
FOOD = {"category": "food", "month": NOVEMBER, "limit": "200.00"}
FOOD_80 = SentWarning(Category.FOOD, NOVEMBER, BUDGET_WARNING)
FOOD_100 = SentWarning(Category.FOOD, NOVEMBER, BUDGET_EXCEEDED)


@pytest.fixture
def db_path(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / "regression.sqlite3"
    db.init_db(path, seed=True)
    yield path
    app.dependency_overrides.clear()


def client_for(path: Path) -> TestClient:
    """A brand-new store on the same file, like a backend that was restarted."""
    store = LedgerStore(SqliteRepository(path), today=lambda: TODAY)
    app.dependency_overrides[get_store] = lambda: store
    return TestClient(app)


def spend(client: TestClient, amount: str) -> dict[str, Any]:
    body = {
        "kind": "expense",
        "account_id": 1,
        "amount": amount,
        "date": "2026-11-10",
        "category": "food",
    }
    response = client.post("/api/transactions", json=body)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def delete(client: TestClient, transaction: dict[str, Any]) -> None:
    assert client.delete(f"/api/accounts/1/transactions/{transaction['id']}").status_code == 200


def messages(created: dict[str, Any]) -> list[str]:
    return [w["message"] for w in created["warnings"]]


# --- 1. warning history is stored -----------------------------------------------------------


def test_deleting_and_re_adding_the_crossing_expense_does_not_repeat_the_warning(
    db_path: Path,
) -> None:
    client = client_for(db_path)
    client.put("/api/budgets", json=FOOD)
    spend(client, "85.50")  # 150.00 spent, 75%
    crossing = spend(client, "15.00")
    assert messages(crossing) == ["FOOD budget at 82%"]

    delete(client, crossing)
    assert messages(spend(client, "15.00")) == []  # the same crossing, already reported


def test_the_history_survives_a_restart(db_path: Path) -> None:
    client = client_for(db_path)
    client.put("/api/budgets", json=FOOD)
    crossing = spend(client, "100.50")  # 165.00 spent
    assert messages(crossing) == ["FOOD budget at 82%"]
    delete(client, crossing)

    restarted = client_for(db_path)  # a new store and a new monitor on the same file
    assert messages(spend(restarted, "100.50")) == []
    assert SqliteRepository(db_path).load_sent_warnings() == {FOOD_80}


def test_the_100_percent_warning_is_not_repeated_either(db_path: Path) -> None:
    client = client_for(db_path)
    client.put("/api/budgets", json=FOOD)
    over = spend(client, "140.00")  # 204.50 spent: past both levels in one step
    assert messages(over) == ["FOOD budget at 102%"]
    delete(client, over)
    assert messages(spend(client, "140.00")) == []
    # Reaching 100% also covers 80%: a smaller expense that only passes 80% stays silent.
    assert SqliteRepository(db_path).load_sent_warnings() == {FOOD_80, FOOD_100}


def test_a_level_that_was_not_reported_yet_is_still_reported(db_path: Path) -> None:
    client = client_for(db_path)
    client.put("/api/budgets", json=FOOD)
    crossing = spend(client, "100.50")
    delete(client, crossing)
    assert messages(spend(client, "140.00")) == ["FOOD budget at 102%"]  # 100% is new


def test_other_months_and_categories_keep_their_own_history(db_path: Path) -> None:
    client = client_for(db_path)
    client.put("/api/budgets", json=FOOD)
    client.put("/api/budgets", json={"category": "food", "month": "2026-12", "limit": "100.00"})
    spend(client, "100.50")
    december = {
        "kind": "expense",
        "account_id": 1,
        "amount": "85.00",
        "date": "2026-12-03",
        "category": "food",
    }
    created = client.post("/api/transactions", json=december).json()
    assert messages(created) == ["FOOD budget at 85%"]


def test_a_new_limit_or_a_removed_budget_starts_a_new_history(db_path: Path) -> None:
    client = client_for(db_path)
    client.put("/api/budgets", json=FOOD)
    crossing = spend(client, "100.50")
    delete(client, crossing)

    client.put("/api/budgets", json=FOOD)  # the same limit again: nothing is forgotten
    assert SqliteRepository(db_path).load_sent_warnings() == {FOOD_80}

    client.put("/api/budgets", json={**FOOD, "limit": "300.00"})  # 80% is now 240.00
    assert SqliteRepository(db_path).load_sent_warnings() == set()
    assert messages(spend(client, "180.00")) == ["FOOD budget at 81%"]

    assert client.delete("/api/budgets/2026-11/food").status_code == 200
    assert SqliteRepository(db_path).load_sent_warnings() == set()


def test_a_failed_request_remembers_nothing(db_path: Path) -> None:
    client = client_for(db_path)
    client.put("/api/budgets", json=FOOD)
    bad = client.post(
        "/api/transactions",
        json={"kind": "expense", "account_id": 99, "amount": "500", "date": "2026-11-10"},
    )
    assert bad.status_code == 404
    assert SqliteRepository(db_path).load_sent_warnings() == set()
    assert messages(spend(client, "100.50")) == ["FOOD budget at 82%"]


def test_monitor_starts_from_the_history_it_is_given() -> None:
    ledger = Ledger()
    ledger.open_account("Checking", AccountType.BANK, Money.of("1000.00"))
    food = Budget(Category.FOOD, NOVEMBER, Money.of("200.00"))
    warnings: list[BudgetWarning] = []
    monitor = BudgetMonitor(ledger, [food], warnings.append, sent={FOOD_80})
    ledger.subscribe(monitor)

    def add(amount: str) -> None:
        expense = Expense(
            id=ledger.next_transaction_id(),
            account_id=1,
            amount=Money.of(amount),
            date=dt.date(2026, 11, 10),
            category=Category.FOOD,
        )
        ledger.add_transaction(1, expense)

    add("165.00")  # crosses 80%, which the history says was already sent
    assert warnings == []
    assert monitor.sent == {FOOD_80}
    add("40.00")  # crosses 100%, which is new
    assert [w.message for w in warnings] == ["FOOD budget at 102%"]
    assert monitor.sent == {FOOD_80, FOOD_100}


def test_forget_changed_keeps_only_unchanged_budgets() -> None:
    food = Budget(Category.FOOD, NOVEMBER, Money.of("200.00"))
    rent = Budget(Category.RENT, NOVEMBER, Money.of("600.00"))
    fun = Budget(Category.FUN, NOVEMBER, Money.of("50.00"))
    rent_100 = SentWarning(Category.RENT, NOVEMBER, BUDGET_EXCEEDED)
    fun_80 = SentWarning(Category.FUN, NOVEMBER, BUDGET_WARNING)
    after = [food, Budget(Category.RENT, NOVEMBER, Money.of("700.00"))]  # rent changed, fun gone
    assert forget_changed({FOOD_80, rent_100, fun_80}, [food, rent, fun], after) == {FOOD_80}


REPOSITORIES: dict[str, Callable[[Path], Repository]] = {
    "csv": lambda p: CsvRepository(p / "csv"),
    "json": lambda p: JsonRepository(p / "pft.json"),
    "sqlite": lambda p: SqliteRepository(p / "pft.sqlite3"),
}


@pytest.mark.parametrize("name", list(REPOSITORIES))
def test_every_repository_keeps_the_warning_history(name: str, tmp_path: Path) -> None:
    repo = REPOSITORIES[name](tmp_path)
    assert repo.load_sent_warnings() == set()
    repo.save_sent_warnings({FOOD_80, FOOD_100})
    ledger = Ledger()
    ledger.open_account("Checking", AccountType.BANK, Money.of("100.00"))
    repo.save(ledger)  # saving the Ledger or the budgets must not lose the history
    repo.save_budgets([Budget(Category.FOOD, NOVEMBER, Money.of("200.00"))])
    assert repo.load_sent_warnings() == {FOOD_80, FOOD_100}
    assert [a.name for a in repo.load().accounts] == ["Checking"]
    repo.save_sent_warnings({FOOD_100})
    assert repo.load_sent_warnings() == {FOOD_100}


def test_sent_warning_rows() -> None:
    assert FOOD_80.to_row() == {"category": "food", "month": NOVEMBER, "level": "80"}
    assert SentWarning.from_row(FOOD_100.to_row()) == FOOD_100
    with pytest.raises(DataImportError):
        SentWarning.from_row({"category": "food", "month": NOVEMBER, "level": "90"})
    with pytest.raises(DataImportError):
        SentWarning.from_row({"category": "food", "month": NOVEMBER})


def test_cli_stores_the_history_between_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "cli.sqlite3"
    monkeypatch.setenv(db.DB_PATH_ENV, str(path))

    def run(*argv: str) -> str:
        assert main(list(argv)) == 0
        return capsys.readouterr().out

    run("account", "add", "Bank", "--opening", "1000")
    run("budget", "set", "food", "200", "--month", NOVEMBER)
    assert "Warning: FOOD budget at 82%" in run(
        "add", "expense", "165", "food", "--date", "2026-11-10"
    )
    repo = SqliteRepository(path)
    assert repo.load_sent_warnings() == {FOOD_80}

    # Take the crossing expense out, as the API's delete does, then add it in a new run.
    ledger = repo.load()
    ledger.remove_transaction(1, 1)
    repo.save(ledger)
    assert "Warning" not in run("add", "expense", "165", "food", "--date", "2026-11-10")

    run("budget", "set", "food", "400", "--month", NOVEMBER)  # a new limit forgets the history
    assert repo.load_sent_warnings() == set()


# --- 2. budget months match the report API -------------------------------------------------

MONTHS = [
    ("0000-01", False),
    ("0001-01", False),
    ("1899-12", False),
    ("1900-01", True),
    ("2026-11", True),
    ("9998-12", True),
    ("9999-01", False),
    ("2026-13", False),
    ("2026-1", False),
]


def test_budgets_and_reports_share_one_pair_of_year_limits() -> None:
    assert (MIN_YEAR, MAX_YEAR) == (1900, 9998)
    assert reports.MIN_YEAR is budget_module.MIN_YEAR
    assert reports.MAX_YEAR is budget_module.MAX_YEAR


@pytest.mark.parametrize(("month", "valid"), MONTHS)
def test_budget_accepts_exactly_the_months_a_report_accepts(month: str, valid: bool) -> None:
    def accepted(build: Callable[[], object]) -> bool:
        try:
            build()
        except (BudgetError, InvalidDateError):
            return False
        return True

    as_budget = accepted(lambda: Budget(Category.FOOD, month, Money.of("10.00")))
    as_report = accepted(lambda: reports.BudgetReport(Ledger(), [], month))
    assert as_budget is as_report is valid


def test_a_year_out_of_range_names_the_month_field() -> None:
    with pytest.raises(BudgetError, match="year must be 1900 to 9998, got 0") as caught:
        Budget(Category.FOOD, "0000-01", Money.of("10.00"))
    assert (caught.value.field, caught.value.code) == ("month", "budget_error")


@pytest.mark.parametrize(("month", "valid"), MONTHS)
def test_budget_routes_and_the_report_route_agree_on_the_month(
    db_path: Path, month: str, valid: bool
) -> None:
    client = client_for(db_path)
    expected = 200 if valid else 422
    saved = client.put("/api/budgets", json={"category": "food", "month": month, "limit": "10"})
    listed = client.get("/api/budgets", params={"month": month})
    report = client.get("/api/reports/budget", params={"month": month})
    assert (saved.status_code, listed.status_code, report.status_code) == (expected,) * 3
    if valid:
        assert [row["category"] for row in report.json()["rows"]] == ["food"]
    else:
        assert saved.json()["field"] == listed.json()["field"] == report.json()["field"] == "month"
        assert SqliteRepository(db_path).load_budgets() == []  # nothing was stored


def test_cli_rejects_a_budget_month_the_report_cannot_show(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(db.DB_PATH_ENV, str(tmp_path / "cli.sqlite3"))
    assert main(["budget", "set", "food", "10", "--month", "0000-01"]) == 1
    assert "year must be 1900 to 9998" in capsys.readouterr().err


def test_a_stored_budget_with_a_bad_year_is_reported_not_hidden(tmp_path: Path) -> None:
    folder = tmp_path / "csv"
    folder.mkdir()
    (folder / "budgets.csv").write_text(
        "category,month,limit,currency\nfood,0000-01,10.00,EUR\n", encoding="utf-8"
    )
    with pytest.raises(DataImportError, match="budget 1"):
        CsvRepository(folder).load_budgets()
