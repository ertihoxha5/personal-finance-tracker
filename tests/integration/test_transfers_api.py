"""POST /api/transfers (#23) on a real SQLite file. Synthetic seed: Checking 3035.50 (ID 1),
Savings 5000.00 (ID 2)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from pft.api.main import app
from pft.api.store import LedgerStore, get_store
from pft.infrastructure import db
from pft.infrastructure.repository import SqliteRepository


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    path = tmp_path / "transfers.sqlite3"
    db.init_db(path, seed=True)
    store = LedgerStore(SqliteRepository(path))
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def balances(client: TestClient) -> dict[str, str]:
    return {a["name"]: a["balance"] for a in client.get("/api/accounts").json()}


def transfer(client: TestClient, **overrides: object) -> Response:
    body = {"from_account_id": 1, "to_account_id": 2, "amount": "35.50", "date": "2026-11-21"}
    response: Response = client.post("/api/transfers", json={**body, **overrides})
    return response


def test_transfer_moves_money_and_keeps_net_worth(client: TestClient) -> None:
    before = client.get("/api/net-worth").json()
    result = transfer(client, note="To savings")
    assert result.status_code == 201
    out_side, in_side = result.json()
    assert (out_side["direction"], in_side["direction"]) == ("out", "in")
    assert (out_side["account_id"], in_side["account_id"]) == (1, 2)
    assert out_side["kind"] == in_side["kind"] == "transfer"
    assert out_side["transfer_id"] == in_side["transfer_id"]
    assert out_side["amount"] == "35.50" and out_side["note"] == "To savings"
    assert balances(client) == {"Checking": "3000.00", "Savings": "5035.50"}
    assert client.get("/api/net-worth").json() == before


def test_same_account_is_rejected_and_nothing_saved(client: TestClient) -> None:
    result = transfer(client, to_account_id=1)
    assert result.status_code == 422
    assert result.json() == {
        "code": "invalid_transfer",
        "message": "choose two different accounts for a transfer",
        "field": "to_account_id",
    }
    assert balances(client) == {"Checking": "3035.50", "Savings": "5000.00"}


def test_amount_above_balance_is_rejected(client: TestClient) -> None:
    result = transfer(client, amount="3035.51")
    assert result.status_code == 422
    body = result.json()
    assert (body["code"], body["field"]) == ("invalid_transfer", "amount")
    assert balances(client)["Checking"] == "3035.50"


@pytest.mark.parametrize(
    ("overrides", "code", "field"),
    [
        ({"amount": "abc"}, "invalid_amount", "amount"),
        ({"amount": "0"}, "invalid_amount", None),
        ({"date": "21/11/2026"}, "invalid_date", "date"),
    ],
)
def test_bad_input_uses_the_error_shape(
    client: TestClient, overrides: dict[str, str], code: str, field: str | None
) -> None:
    result = transfer(client, **overrides)
    body = result.json()
    assert result.status_code == 422
    assert body["code"] == code
    if field is not None:
        assert body["field"] == field


def test_unknown_account_is_404(client: TestClient) -> None:
    assert transfer(client, to_account_id=99).status_code == 404


def test_transfers_stay_out_of_dashboard_income_and_expense(client: TestClient) -> None:
    """The month's income/expense totals are the same before and after a transfer."""

    def totals() -> object:
        return client.get("/api/dashboard", params={"month": "2026-11"}).json()["summary"]

    before = totals()
    assert transfer(client).status_code == 201
    assert totals() == before


def test_deleting_one_side_deletes_both_and_survives_restart(client: TestClient) -> None:
    in_side = transfer(client).json()[1]
    rows = client.get("/api/transactions", params={"kind": "transfer"}).json()
    assert len(rows) == 2
    deleted = client.delete(f"/api/accounts/2/transactions/{in_side['id']}")
    assert deleted.status_code == 200
    assert client.get("/api/transactions", params={"kind": "transfer"}).json() == []
    assert balances(client) == {"Checking": "3035.50", "Savings": "5000.00"}
