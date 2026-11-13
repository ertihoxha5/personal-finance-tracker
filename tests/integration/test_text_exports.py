"""Task #24 approved download formats share the existing snapshot contract."""

from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from pft.api.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as session:
        yield session


def payload(fmt: str) -> dict[str, object]:
    return {
        "filename": f"filtered.{fmt}",
        "columns": ["note", "amount"],
        "rows": [{"amount": "12.50", "note": "=SUM(A1)"}],
        "filters": {"note": "lunch", "sortDirection": "desc"},
    }


def test_json_attachment_preserves_text_amounts_and_column_order(client: TestClient) -> None:
    response = client.post("/api/exports/json", json=payload("json"))
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["content-disposition"] == 'attachment; filename="filtered.json"'
    assert response.json() == [{"note": "=SUM(A1)", "amount": "12.50"}]
    assert list(response.json()[0]) == ["note", "amount"]
    assert '\n  {\n    "note"' in response.text


def test_markdown_attachment_is_a_table(client: TestClient) -> None:
    response = client.post("/api/exports/md", json=payload("md"))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.headers["content-disposition"] == 'attachment; filename="filtered.md"'
    assert response.text == "| note | amount |\n| --- | --- |\n| =SUM(A1) | 12.50 |\n"


@pytest.mark.parametrize("fmt", ["json", "md"])
def test_empty_text_exports_work(client: TestClient, fmt: str) -> None:
    body = payload(fmt)
    body["rows"] = []
    response = client.post(f"/api/exports/{fmt}", json=body)
    assert response.status_code == 200
    assert response.json() == [] if fmt == "json" else response.text.count("\n") == 2


@pytest.mark.parametrize("fmt", ["json", "md"])
@pytest.mark.parametrize("filename", ["../report.json", "report.json\r\nX: bad", "report.csv"])
def test_bad_text_filenames_are_rejected(client: TestClient, fmt: str, filename: str) -> None:
    body = payload(fmt)
    body["filename"] = filename
    assert client.post(f"/api/exports/{fmt}", json=body).status_code == 422


def test_format_must_match_filename_and_be_approved(client: TestClient) -> None:
    assert client.post("/api/exports/json", json=payload("md")).status_code == 422
    assert client.post("/api/exports/xml", json=payload("json")).status_code == 404


@pytest.mark.parametrize("fmt", ["json", "md"])
def test_text_export_retains_schema_validation(client: TestClient, fmt: str) -> None:
    body = payload(fmt)
    body["columns"] = ["note", "note"]
    assert client.post(f"/api/exports/{fmt}", json=body).status_code == 422


def test_text_export_failure_has_recoverable_message(client: TestClient) -> None:
    with patch("pft.infrastructure.exporters.JsonExporter.export", side_effect=OSError("private")):
        response = client.post("/api/exports/json", json=payload("json"))
    assert response.status_code == 500
    assert response.json() == {"detail": "The export could not be created. Try again."}
