"""End-to-end flow behind the four React screens (#36), on synthetic data only.

One real SQLite file is used for the whole test. The "backend restart" builds a brand-new
store and repository on the same file, which is what happens when ``pft serve`` is stopped
and started again. The React screens only call these routes, so this covers their contract.
"""

import datetime as dt
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from pft.api.main import app
from pft.api.store import LedgerStore, get_store
from pft.infrastructure import db
from pft.infrastructure.repository import SqliteRepository

TODAY = dt.date(2026, 11, 15)
MONTH = "2026-11"


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "flow.sqlite3"
    db.init_db(path, seed=False)
    return path


@pytest.fixture
def restart(database: Path) -> Iterator[Callable[[], TestClient]]:
    """Return a function that starts a fresh 'backend' on the same database file."""

    def start() -> TestClient:
        store = LedgerStore(SqliteRepository(database), today=lambda: TODAY)
        app.dependency_overrides[get_store] = lambda: store
        return TestClient(app)

    yield start
    app.dependency_overrides.clear()


def ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def test_screens_flow_survives_a_backend_restart(restart: Callable[[], TestClient]) -> None:
    client = restart()

    # Accounts screen: create, rename.
    checking = ok(
        client.post(
            "/api/accounts",
            json={"name": "Checking", "type": "bank", "opening_balance": "1000.00"},
        ),
        201,
    )
    savings = ok(
        client.post(
            "/api/accounts",
            json={"name": "Savings", "type": "savings", "opening_balance": "0"},
        ),
        201,
    )
    spare = ok(
        client.post(
            "/api/accounts", json={"name": "Spare", "type": "cash", "opening_balance": "5.00"}
        ),
        201,
    )
    ok(client.patch(f"/api/accounts/{spare['id']}", json={"name": "Wallet"}))

    # Budgets screen: a food limit, then spending moves usage and raises the 80% warning.
    ok(client.put("/api/budgets", json={"category": "food", "month": MONTH, "limit": "200.00"}))

    # Transactions screen: create, edit, delete.
    def spend(amount: str) -> dict[str, Any]:
        body = {
            "kind": "expense",
            "account_id": checking["id"],
            "amount": amount,
            "date": "2026-11-10",
            "category": "food",
            "note": "synthetic",
        }
        result: dict[str, Any] = ok(client.post("/api/transactions", json=body), 201)
        return result

    first = spend("100.00")
    assert first["warnings"] == []
    second = spend("70.00")
    assert [w["level"] for w in second["warnings"]] == [80]  # 170.00 of 200.00 is 85%

    edit = {"kind": "expense", "amount": "60.00", "date": "2026-11-10", "note": "edited"}
    edited = ok(
        client.put(f"/api/accounts/{checking['id']}/transactions/{second['id']}", json=edit)
    )
    assert edited["amount"] == "60.00"
    third = spend("5.00")
    ok(client.delete(f"/api/accounts/{checking['id']}/transactions/{third['id']}"))

    # Transfer: both sides exist and the balances move by the same amount.
    sides = ok(
        client.post(
            "/api/transfers",
            json={
                "from_account_id": checking["id"],
                "to_account_id": savings["id"],
                "amount": "250.00",
                "date": "2026-11-12",
            },
        ),
        201,
    )
    assert len(sides) == 2

    # Closing an unused account works.
    ok(client.delete(f"/api/accounts/{spare['id']}"))

    def snapshot(c: TestClient) -> dict[str, Any]:
        accounts = ok(c.get("/api/accounts"))
        return {
            "balances": {a["name"]: a["balance"] for a in accounts},
            "budget": ok(c.get("/api/budgets", params={"month": MONTH}))["budgets"],
            "transactions": ok(c.get("/api/transactions")),
            "dashboard": ok(c.get("/api/dashboard", params={"month": MONTH})),
        }

    before = snapshot(client)
    # 1000 - 100 - 60 (edited) - 250 transfer; savings gets the 250.
    assert before["balances"] == {"Checking": "590.00", "Savings": "250.00"}
    assert before["budget"][0]["spent"] == "160.00"
    assert before["budget"][0]["status"] == "warning"

    # Backend restart: nothing is lost and nothing is added a second time.
    after = snapshot(restart())
    assert after == before

    # Export: the Transactions screen posts its visible rows and gets a file back.
    rows = [
        {"id": t["id"], "amount": t["amount"], "category": t["category"]}
        for t in after["transactions"]
    ]
    response = restart().post(
        "/api/exports/csv",
        json={"columns": ["id", "amount", "category"], "rows": rows, "filename": "t.csv"},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-disposition"] == 'attachment; filename="t.csv"'
    assert len(response.text.strip().splitlines()) == len(rows) + 1


def test_bad_input_returns_the_error_shape_the_screens_show(
    restart: Callable[[], TestClient],
) -> None:
    client = restart()
    body = ok(
        client.post(
            "/api/accounts", json={"name": "A", "type": "bank", "opening_balance": "10.00"}
        ),
        201,
    )
    bad = client.post(
        "/api/transactions",
        json={"kind": "expense", "account_id": body["id"], "amount": "abc", "date": "2026-11-10"},
    )
    assert bad.status_code == 422
    assert set(bad.json()) == {"code", "message", "field"}
    missing = client.delete("/api/accounts/999")
    assert missing.status_code == 404
