"""Accounts API on a real SQLite file, including a simulated backend restart (#18)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pft.api.main import app
from pft.api.store import LedgerStore, get_store
from pft.infrastructure import db
from pft.infrastructure.repository import SqliteRepository


def make_client(path: Path) -> TestClient:
    """A client with a brand-new store, like a freshly started backend on the same file."""
    store = LedgerStore(SqliteRepository(path))
    app.dependency_overrides[get_store] = lambda: store
    return TestClient(app)


@pytest.fixture
def db_path(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / "api.sqlite3"
    db.init_db(path, seed=True)
    yield path
    app.dependency_overrides.clear()


def test_lists_accounts_with_balances_from_the_ledger(db_path: Path) -> None:
    client = make_client(db_path)
    accounts = {a["name"]: a for a in client.get("/api/accounts").json()}
    assert accounts["Checking"]["balance"] == "3035.50"  # 1500 + 2200 - 64.50 - 600
    assert accounts["Checking"]["transaction_count"] == 3
    assert accounts["Savings"]["balance"] == "5000.00"


def test_net_worth_is_the_sum_of_balances(db_path: Path) -> None:
    body = make_client(db_path).get("/api/net-worth").json()
    assert body == {"currency": "EUR", "net_worth": "8035.50", "account_count": 2}


def test_empty_database_gives_empty_lists_and_zero(tmp_path: Path) -> None:
    client = make_client(tmp_path / "none.sqlite3")
    try:
        assert client.get("/api/accounts").json() == []
        assert client.get("/api/net-worth").json()["net_worth"] == "0.00"
    finally:
        app.dependency_overrides.clear()


def test_changes_survive_a_backend_restart(db_path: Path) -> None:
    client = make_client(db_path)
    created = client.post(
        "/api/accounts", json={"name": "Wallet", "type": "cash", "opening_balance": "20.00"}
    )
    assert created.status_code == 201
    wallet = created.json()["id"]
    response = client.post(
        "/api/transactions",
        json={"kind": "expense", "account_id": wallet, "amount": "4,50", "date": "2026-11-10",
              "category": "food", "note": "Lunch"},
    )
    assert response.status_code == 201
    assert response.json()["id"] == 4  # the seed has transactions 1..3
    client.delete("/api/accounts/1/transactions/2")  # remove Groceries
    renamed = client.patch("/api/accounts/2", json={"name": "Rainy day"})
    assert renamed.json()["name"] == "Rainy day"

    restarted = make_client(db_path)  # new store, same file
    accounts = {a["name"]: a for a in restarted.get("/api/accounts").json()}
    assert accounts["Wallet"]["balance"] == "15.50"
    assert accounts["Checking"]["balance"] == "3100.00"  # 1500 + 2200 - 600
    assert "Rainy day" in accounts
    txs = restarted.get(f"/api/accounts/{wallet}/transactions").json()
    assert [(t["amount"], t["note"], t["kind"]) for t in txs] == [("4.50", "Lunch", "expense")]
    assert restarted.get("/api/net-worth").json()["net_worth"] == "8115.50"


def test_edit_transaction_changes_balance_and_keeps_id(db_path: Path) -> None:
    client = make_client(db_path)
    response = client.put(
        "/api/accounts/1/transactions/2",
        json={"kind": "expense", "amount": "100.00", "date": "2026-11-02", "note": "Market"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == 2
    assert response.json()["category"] == "food"  # kept from the stored transaction
    assert make_client(db_path).get("/api/accounts").json()[0]["balance"] == "3000.00"


def test_errors_use_the_code_message_field_shape(db_path: Path) -> None:
    client = make_client(db_path)
    bad_amount = client.post(
        "/api/transactions",
        json={"kind": "expense", "account_id": 1, "amount": "abc", "date": "2026-11-10"},
    )
    assert bad_amount.status_code == 422
    assert bad_amount.json()["code"] == "invalid_amount"
    assert bad_amount.json()["field"] == "amount"

    missing = client.get("/api/accounts/99/transactions")
    assert missing.status_code == 404
    assert missing.json()["code"] == "account_not_found"

    malformed = client.post("/api/accounts", json={"name": "X"})
    assert malformed.status_code == 422
    assert set(malformed.json()) == {"code", "message", "field"}


def test_a_rejected_change_is_not_saved(db_path: Path) -> None:
    client = make_client(db_path)
    client.post(
        "/api/transactions",
        json={"kind": "expense", "account_id": 1, "amount": "0", "date": "2026-11-10"},
    )
    assert client.get("/api/accounts/1/transactions").json().__len__() == 3


def test_failed_save_reports_storage_error_and_keeps_old_data(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client(db_path)

    def broken_save(self: SqliteRepository, ledger: object) -> None:
        from pft.domain.exceptions import StorageError

        raise StorageError("disk full")

    monkeypatch.setattr(SqliteRepository, "save", broken_save)
    response = client.delete("/api/accounts/1")
    assert response.status_code == 500
    assert response.json()["code"] == "storage_error"
    monkeypatch.undo()
    assert len(make_client(db_path).get("/api/accounts").json()) == 2


def test_transfer_cannot_be_edited_alone(tmp_path: Path) -> None:
    path = tmp_path / "t.sqlite3"
    db.init_db(path, seed=True)
    conn = db.connect(path)
    with conn:
        conn.execute(
            "INSERT INTO transactions (account_id, kind, amount_cents, occurred_on, "
            "transfer_id, direction) VALUES (1, 'transfer', 5000, '2026-11-04', 't-1', 'out')"
        )
    conn.close()
    client = make_client(path)
    try:
        response = client.put(
            "/api/accounts/1/transactions/4",
            json={"kind": "expense", "amount": "1.00", "date": "2026-11-04"},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "invalid_transfer"
    finally:
        app.dependency_overrides.clear()
