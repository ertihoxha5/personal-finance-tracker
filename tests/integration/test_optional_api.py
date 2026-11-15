"""Optional tools are gated, transactional and isolated from the core routes."""

import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from pft.api.main import app
from pft.api.store import LedgerStore, get_store
from pft.domain.exceptions import StorageError
from pft.infrastructure import db
from pft.infrastructure.repository import SqliteRepository

CSV = "date,amount,category,note\n2026-11-15,-12.50,food,Lunch\n2026-02-30,4,food,Bad date\n"
ADD = {
    "action": "add",
    "transaction": {
        "kind": "expense",
        "account_id": 1,
        "amount": "12.50",
        "date": "2026-11-15",
        "category": "food",
        "note": "Tools test",
    },
}


@pytest.fixture
def setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, SqliteRepository]]:
    monkeypatch.setenv("PFT_OPTIONAL_FEATURES", "undo,import,charts")
    path = tmp_path / "optional.sqlite3"
    db.init_db(path, seed=True)
    repository = SqliteRepository(path)
    store = LedgerStore(repository, today=lambda: dt.date(2026, 11, 15))
    app.dependency_overrides[get_store] = lambda: store
    try:
        with TestClient(app) as client:
            yield client, repository
    finally:
        app.dependency_overrides.clear()


def start(client: TestClient) -> str:
    response = client.post("/api/optional/history")
    assert response.status_code == 200, response.text
    token: str = response.json()["token"]
    return token


def test_features_default_off_without_breaking_core(
    setup: tuple[TestClient, SqliteRepository], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = setup
    monkeypatch.delenv("PFT_OPTIONAL_FEATURES")
    assert client.get("/api/optional/features").json() == {
        "undo": False,
        "import": False,
        "charts": False,
    }
    assert client.post("/api/optional/history").status_code == 404
    assert (
        client.post(
            "/api/optional/import/preview", json={"account_id": 1, "csv_text": CSV}
        ).status_code
        == 404
    )
    assert client.get("/api/optional/charts/trend?end=2026-11").status_code == 404
    assert client.get("/api/accounts").status_code == 200


def test_history_add_undo_redo_persists_and_new_operation_clears_redo(
    setup: tuple[TestClient, SqliteRepository],
) -> None:
    client, repo = setup
    token = start(client)
    path = f"/api/optional/history/{token}"
    before = len(list(repo.load().all_transactions()))
    result = client.post(path, json=ADD)
    assert result.status_code == 200, result.text
    assert result.json()["can_undo"]
    assert len(list(repo.load().all_transactions())) == before + 1
    assert client.post(path, json={"action": "undo"}).json()["can_redo"]
    assert len(list(repo.load().all_transactions())) == before
    assert client.post(path, json={"action": "redo"}).status_code == 200
    assert len(list(repo.load().all_transactions())) == before + 1
    client.post(path, json={"action": "undo"})
    assert client.post(path, json=ADD).json()["can_redo"] is False


def test_failed_save_does_not_advance_history(setup: tuple[TestClient, SqliteRepository]) -> None:
    client, repo = setup
    path = f"/api/optional/history/{start(client)}"
    before = len(list(repo.load().all_transactions()))
    with patch.object(repo, "save", side_effect=StorageError("Save failed")):
        response = client.post(path, json=ADD)
    assert response.status_code == 500
    assert client.get(path).json()["can_undo"] is False
    assert len(list(repo.load().all_transactions())) == before
    assert client.post(path, json=ADD).status_code == 200


def test_failed_undo_save_keeps_history_retryable(
    setup: tuple[TestClient, SqliteRepository],
) -> None:
    client, repo = setup
    path = f"/api/optional/history/{start(client)}"
    assert client.post(path, json=ADD).status_code == 200
    count = len(list(repo.load().all_transactions()))
    with patch.object(repo, "save", side_effect=StorageError("Save failed")):
        assert client.post(path, json={"action": "undo"}).status_code == 500
    assert client.get(path).json()["can_undo"] is True
    assert len(list(repo.load().all_transactions())) == count
    assert client.post(path, json={"action": "undo"}).status_code == 200


def test_core_mutation_invalidates_history_and_rejects_stale_click(
    setup: tuple[TestClient, SqliteRepository],
) -> None:
    client, _ = setup
    path = f"/api/optional/history/{start(client)}"
    client.post(path, json=ADD)
    assert client.post("/api/transactions", json=ADD["transaction"]).status_code == 201
    response = client.post(path, json={"action": "undo"})
    assert response.status_code == 422
    assert response.json()["code"] == "command_error"
    reset = client.get(path).json()
    assert reset["can_undo"] is False
    assert reset["can_redo"] is False
    assert reset["reset"] is True


def test_preview_and_confirm_revalidate_and_cannot_be_replayed(
    setup: tuple[TestClient, SqliteRepository],
) -> None:
    client, repo = setup
    body = {"account_id": 1, "csv_text": CSV}
    before = len(list(repo.load().all_transactions()))
    response = client.post("/api/optional/import/preview", json=body)
    assert response.status_code == 200, response.text
    preview = response.json()
    assert len(preview["accepted"]) == 1
    assert preview["errors"][0]["row_number"] == 3
    assert len(list(repo.load().all_transactions())) == before
    confirmed = {**body, "expected_revision": preview["revision"]}
    response = client.post("/api/optional/import/confirm", json=confirmed)
    assert response.status_code == 200
    assert len(list(repo.load().all_transactions())) == before + 1
    assert client.post("/api/optional/import/confirm", json=confirmed).status_code == 422


def test_confirmation_requires_fresh_preview(setup: tuple[TestClient, SqliteRepository]) -> None:
    client, _ = setup
    body = {"account_id": 1, "csv_text": CSV}
    assert client.post("/api/optional/import/confirm", json=body).status_code == 422
    preview = client.post("/api/optional/import/preview", json=body).json()
    client.post("/api/transactions", json=ADD["transaction"])
    assert (
        client.post(
            "/api/optional/import/confirm", json={**body, "expected_revision": preview["revision"]}
        ).status_code
        == 422
    )


def test_transfer_and_delete_are_paired_history_operations(
    setup: tuple[TestClient, SqliteRepository],
) -> None:
    client, repo = setup
    path = f"/api/optional/history/{start(client)}"
    before = list(repo.load().all_transactions())
    response = client.post(
        path,
        json={
            "action": "transfer",
            "transfer": {
                "from_account_id": 1,
                "to_account_id": 2,
                "amount": "10.00",
                "date": "2026-11-15",
            },
        },
    )
    assert response.status_code == 200, response.text
    latest = max(repo.load().all_transactions(), key=lambda t: t.id)
    response = client.post(
        path, json={"action": "delete", "account_id": 2, "transaction_id": latest.id}
    )
    assert response.status_code == 200, response.text
    assert len(list(repo.load().all_transactions())) == len(before)
    assert client.post(path, json={"action": "undo"}).status_code == 200
    assert len(list(repo.load().all_transactions())) == len(before) + 2


@pytest.mark.parametrize(
    "url", ["categories?start=2026-11-01&end=2026-11-30", "trend?end=2026-11&months=6"]
)
def test_chart_downloads_are_pngs(setup: tuple[TestClient, SqliteRepository], url: str) -> None:
    pytest.importorskip("matplotlib")
    client, _ = setup
    response = client.get("/api/optional/charts/" + url)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/png"
    assert ".png" in response.headers["content-disposition"]
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_invalid_chart_filters_and_expired_sessions_are_friendly(
    setup: tuple[TestClient, SqliteRepository],
) -> None:
    client, _ = setup
    assert client.get("/api/optional/charts/trend?end=0000-01").status_code == 422
    assert client.get("/api/optional/charts/trend?end=2026-11&months=0").status_code == 422
    assert (
        client.get("/api/optional/charts/categories?start=2026-11-30&end=2026-11-01").status_code
        == 422
    )
    assert client.get("/api/optional/history/expired").status_code == 422


def test_second_browser_cannot_replay_stale_history(
    setup: tuple[TestClient, SqliteRepository],
) -> None:
    client, _ = setup
    first = f"/api/optional/history/{start(client)}"
    second = f"/api/optional/history/{start(client)}"
    assert client.post(first, json=ADD).status_code == 200
    assert client.post(second, json=ADD).status_code == 422
    assert client.get(second).json()["reset"] is True
    assert client.post(second, json=ADD).status_code == 200
    assert client.post(first, json={"action": "undo"}).status_code == 422


def test_failed_import_save_leaves_preview_retryable(
    setup: tuple[TestClient, SqliteRepository],
) -> None:
    client, repo = setup
    body = {"account_id": 1, "csv_text": CSV}
    preview = client.post("/api/optional/import/preview", json=body).json()
    body["expected_revision"] = preview["revision"]
    before = len(list(repo.load().all_transactions()))
    with patch.object(repo, "save", side_effect=StorageError("Save failed")):
        assert client.post("/api/optional/import/confirm", json=body).status_code == 500
    assert len(list(repo.load().all_transactions())) == before
    assert client.post("/api/optional/import/confirm", json=body).status_code == 200


def test_missing_chart_dependency_is_a_recoverable_service_error(
    setup: tuple[TestClient, SqliteRepository],
) -> None:
    from pft.infrastructure.charts import ChartUnavailableError

    client, _ = setup
    with patch(
        "pft.infrastructure.charts.save_monthly_trend",
        side_effect=ChartUnavailableError("Install charts extra"),
    ):
        response = client.get("/api/optional/charts/trend?end=2026-11")
    assert response.status_code == 503
    assert response.json() == {"detail": "Install charts extra"}
