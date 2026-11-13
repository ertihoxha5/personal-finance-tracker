"""GET /api/reports/categories on a real SQLite file (#26)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pft.api.main import app
from pft.api.store import LedgerStore, get_store
from pft.infrastructure import db
from pft.infrastructure.repository import SqliteRepository

URL = "/api/reports/categories"


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    path = tmp_path / "report.sqlite3"
    db.init_db(path, seed=True)  # November 2026: income 2200, food 64.50, rent 600
    store = LedgerStore(SqliteRepository(path))
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_month_range_gives_amounts_and_percentages(client: TestClient) -> None:
    body = client.get(URL, params={"start": "2026-11-01", "end": "2026-11-30"}).json()
    assert body["currency"] == "EUR"
    assert body["total"] == "664.50"
    assert [(c["category"], c["total"], c["percent"]) for c in body["categories"]] == [
        ("rent", "600.00", "90.3"),
        ("food", "64.50", "9.7"),
    ]


def test_period_without_spending_is_empty_not_an_error(client: TestClient) -> None:
    response = client.get(URL, params={"start": "2025-01-01", "end": "2025-12-31"})
    assert response.status_code == 200
    assert response.json() == {
        "start": "2025-01-01",
        "end": "2025-12-31",
        "currency": "EUR",
        "total": "0.00",
        "categories": [],
    }


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"start": "2026-11-30", "end": "2026-11-01"}, "end"),  # reversed
        ({"start": "2026-02-30", "end": "2026-03-01"}, "start"),  # right shape, not a real day
        ({"start": "20261101", "end": "2026-11-30"}, "start"),  # wrong shape
        ({"start": "2026-11-01", "end": "tomorrow"}, "end"),
    ],
)
def test_bad_dates_return_the_error_shape(
    client: TestClient, params: dict[str, str], field: str
) -> None:
    response = client.get(URL, params=params)
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_date"
    assert body["field"] == field


def test_missing_date_is_a_422_with_the_error_shape(client: TestClient) -> None:
    response = client.get(URL, params={"start": "2026-11-01"})
    assert response.status_code == 422
    assert response.json()["field"] == "end"
