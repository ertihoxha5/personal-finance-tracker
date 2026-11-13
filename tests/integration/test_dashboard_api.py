"""GET /api/dashboard on a real SQLite file (#19)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pft.api.main import app
from pft.api.store import LedgerStore, get_store
from pft.infrastructure import db
from pft.infrastructure.repository import SqliteRepository


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    path = tmp_path / "dash.sqlite3"
    db.init_db(path, seed=True)  # November 2026: income 2200, food 64.50, rent 600
    store = LedgerStore(SqliteRepository(path))
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def add(client: TestClient, kind: str, amount: str, day: str, category: str = "food") -> None:
    response = client.post(
        "/api/transactions",
        json={"kind": kind, "account_id": 1, "amount": amount, "date": day, "category": category},
    )
    assert response.status_code == 201


def test_default_month_is_the_latest_month_with_data(client: TestClient) -> None:
    body = client.get("/api/dashboard").json()
    assert body["month"] == "2026-11"
    assert body["available_months"] == ["2026-11"]
    assert body["summary"] == {
        "income": "2200.00",
        "expenses": "664.50",
        "net": "1535.50",
        "savings_rate": "69.8",
        "transaction_count": 3,
    }
    assert [c["category"] for c in body["top_categories"]] == ["rent", "food"]


def test_previous_month_comparison_and_trend(client: TestClient) -> None:
    add(client, "income", "2000.00", "2026-10-05", "salary")
    add(client, "expense", "500.00", "2026-10-06", "rent")
    body = client.get("/api/dashboard?month=2026-11").json()
    assert body["available_months"] == ["2026-10", "2026-11"]
    assert body["previous"]["month"] == "2026-10"
    assert body["previous"]["net"] == "1500.00"
    assert body["changes"] == {"income": "200.00", "expenses": "164.50", "net": "35.50"}
    trend = {row["month"]: row for row in body["trend"]}
    assert list(trend) == ["2026-07", "2026-08", "2026-09", "2026-10", "2026-11"]
    assert trend["2026-09"]["income"] == "0.00"
    assert trend["2026-10"]["expenses"] == "500.00"


def test_month_without_data_is_all_zeros(client: TestClient) -> None:
    body = client.get("/api/dashboard?month=2026-03").json()
    assert body["summary"]["income"] == "0.00"
    assert body["summary"]["savings_rate"] == "0.0"
    assert body["summary"]["transaction_count"] == 0
    assert body["categories"] == [] and body["recent_transactions"] == []
    assert "2026-03" in body["available_months"]  # the picker still offers it


def test_recent_transactions_are_newest_first_with_account_names(client: TestClient) -> None:
    rows = client.get("/api/dashboard").json()["recent_transactions"]
    assert [r["note"] for r in rows] == ["Rent", "Groceries", "Salary"]
    assert rows[0]["account"] == {"id": 1, "name": "Checking"}
    assert rows[0]["kind"] == "expense" and rows[0]["amount"] == "600.00"


def test_empty_database_gives_an_empty_dashboard(tmp_path: Path) -> None:
    store = LedgerStore(SqliteRepository(tmp_path / "none.sqlite3"))
    app.dependency_overrides[get_store] = lambda: store
    try:
        body = TestClient(app).get("/api/dashboard").json()
    finally:
        app.dependency_overrides.clear()
    assert body["summary"]["net"] == "0.00"
    assert body["recent_transactions"] == []


@pytest.mark.parametrize(
    "month",
    ["2026-13", "2026-1", "november", "2026-11-01", "", "0000-01", "0001-01", "1899-12", "9999-12"],
)
def test_bad_month_uses_the_error_shape(client: TestClient, month: str) -> None:
    response = client.get("/api/dashboard", params={"month": month})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_date"
    assert response.json()["field"] == "month"
