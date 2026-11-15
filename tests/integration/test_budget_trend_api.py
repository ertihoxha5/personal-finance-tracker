"""GET /api/reports/budget and /api/reports/trend on a real SQLite file (#31).

Synthetic seed, November 2026: income 2200.00, food 64.50, rent 600.00. "Today" is fixed at
15 November 2026.
"""

import datetime as dt
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pft.api.main import app
from pft.api.store import LedgerStore, get_store
from pft.infrastructure import db
from pft.infrastructure.repository import SqliteRepository

TODAY = dt.date(2026, 11, 15)
BUDGET = "/api/reports/budget"
TREND = "/api/reports/trend"


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    path = tmp_path / "report.sqlite3"
    db.init_db(path, seed=True)
    store = LedgerStore(SqliteRepository(path), today=lambda: TODAY)
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def set_budget(client: TestClient, category: str, limit: str, month: str = "2026-11") -> None:
    body = {"category": category, "month": month, "limit": limit}
    assert client.put("/api/budgets", json=body).status_code == 200


def test_budget_report_gives_planned_actual_difference_and_status(client: TestClient) -> None:
    set_budget(client, "food", "80.00")  # 64.50 spent: 80.6%
    set_budget(client, "rent", "600.00")  # exactly 100%
    set_budget(client, "fun", "50.00")  # nothing spent
    body = client.get(BUDGET, params={"month": "2026-11"}).json()
    assert body["month"] == "2026-11"
    assert body["currency"] == "EUR"
    assert body["rows"] == [
        {
            "category": "food",
            "planned": "80.00",
            "actual": "64.50",
            "difference": "15.50",
            "usage_percent": "80.6",
            "status": "warning",
        },
        {
            "category": "fun",
            "planned": "50.00",
            "actual": "0.00",
            "difference": "50.00",
            "usage_percent": "0.0",
            "status": "ok",
        },
        {
            "category": "rent",
            "planned": "600.00",
            "actual": "600.00",
            "difference": "0.00",
            "usage_percent": "100.0",
            "status": "over",
        },
    ]
    assert body["totals"] == {"planned": "730.00", "actual": "664.50", "difference": "65.50"}


def test_budget_report_follows_spending_and_shows_overspending(client: TestClient) -> None:
    set_budget(client, "food", "80.00")
    expense = {
        "kind": "expense",
        "account_id": 1,
        "amount": "25.50",
        "date": "2026-11-10",
        "category": "food",
    }
    assert client.post("/api/transactions", json=expense).status_code == 201
    [row] = client.get(BUDGET).json()["rows"]  # the default month is today's
    assert (row["actual"], row["difference"], row["status"]) == ("90.00", "-10.00", "over")


def test_budget_report_for_a_month_without_budgets_is_empty(client: TestClient) -> None:
    set_budget(client, "food", "80.00")
    response = client.get(BUDGET, params={"month": "2026-12"})
    assert response.status_code == 200
    assert response.json() == {
        "month": "2026-12",
        "currency": "EUR",
        "rows": [],
        "totals": {"planned": "0.00", "actual": "0.00", "difference": "0.00"},
    }


def test_budget_report_rejects_a_bad_month(client: TestClient) -> None:
    response = client.get(BUDGET, params={"month": "11/2026"})
    assert response.status_code == 422
    assert (response.json()["code"], response.json()["field"]) == ("invalid_date", "month")


def test_trend_gives_exactly_n_rows_in_date_order(client: TestClient) -> None:
    body = client.get(TREND, params={"months": 6}).json()  # ends with today's month
    assert [row["month"] for row in body["months"]] == [
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
        "2026-10",
        "2026-11",
    ]
    assert body["months"][0] == {
        "month": "2026-06",
        "income": "0.00",
        "expenses": "0.00",
        "net": "0.00",
    }
    assert body["months"][-1] == {
        "month": "2026-11",
        "income": "2200.00",
        "expenses": "664.50",
        "net": "1535.50",
    }


def test_trend_end_month_and_default_length(client: TestClient) -> None:
    body = client.get(TREND, params={"end": "2027-01"}).json()
    assert len(body["months"]) == 6
    assert body["months"][-1]["month"] == "2027-01"
    assert body["months"][-3]["net"] == "1535.50"  # November 2026


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"months": 0}, "months"),
        ({"months": 121}, "months"),
        ({"months": "six"}, "months"),
        ({"end": "2026-13"}, "end"),
        ({"end": "1900-02", "months": 6}, "end"),
    ],
)
def test_trend_rejects_bad_input_with_the_error_shape(
    client: TestClient, params: dict[str, object], field: str
) -> None:
    response = client.get(TREND, params=params)
    assert response.status_code == 422
    assert response.json()["field"] == field
    assert set(response.json()) == {"code", "message", "field"}


def test_dashboard_trend_still_has_its_five_months(client: TestClient) -> None:
    trend = client.get("/api/dashboard", params={"month": "2026-11"}).json()["trend"]
    assert [row["month"] for row in trend] == [
        "2026-07",
        "2026-08",
        "2026-09",
        "2026-10",
        "2026-11",
    ]
    assert trend[-1] == {"month": "2026-11", "income": "2200.00", "expenses": "664.50"}
