"""Task #16 CSV endpoint contracts."""

import csv
import io
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from pft.api.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as session:
        yield session


def test_download_returns_csv_attachment_in_supplied_order(client: TestClient) -> None:
    response = client.post(
        "/api/exports/csv",
        json={
            "filename": "filtered-transactions.csv",
            "columns": ["id", "note", "amount"],
            "rows": [
                {"id": "2", "note": 'Café, "lunch"', "amount": "25.00"},
                {"id": "1", "note": "Lunch", "amount": "12.50"},
            ],
            "filters": {"note": "lunch", "categories": ["Food"], "sortDirection": "desc"},
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="filtered-transactions.csv"'
    )
    reader = csv.DictReader(io.StringIO(response.content.decode("utf-8-sig")))
    assert reader.fieldnames == ["id", "note", "amount"]
    assert list(reader) == [
        {"id": "2", "note": 'Café, "lunch"', "amount": "25.00"},
        {"id": "1", "note": "Lunch", "amount": "12.50"},
    ]


def test_empty_export_keeps_requested_report_header(client: TestClient) -> None:
    response = client.post(
        "/api/exports/csv",
        json={
            "filename": "report.csv",
            "columns": ["month", "value"],
            "rows": [],
            "filters": {"month": "2026-11"},
        },
    )
    assert response.status_code == 200
    assert response.content.decode("utf-8-sig") == "month,value\r\n"


@pytest.mark.parametrize(
    "filename", ["../report.csv", "C:\\report.csv", "report.csv\r\nX-Test: bad", "report.txt", ""]
)
def test_invalid_filename_is_rejected(client: TestClient, filename: str) -> None:
    response = client.post(
        "/api/exports/csv",
        json={
            "filename": filename,
            "columns": ["note"],
            "rows": [],
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "columns, rows",
    [
        ([], []),
        (["note", "note"], []),
        ([" "], []),
        (["note"], [{"other": "value"}]),
    ],
)
def test_malformed_schema_is_rejected(
    client: TestClient,
    columns: list[str],
    rows: list[dict[str, str]],
) -> None:
    response = client.post(
        "/api/exports/csv",
        json={
            "filename": "report.csv",
            "columns": columns,
            "rows": rows,
        },
    )
    assert response.status_code == 422


def test_file_failure_returns_recoverable_error_without_server_paths(client: TestClient) -> None:
    with patch("pft.api.exports.CsvExporter.export", side_effect=OSError("private server path")):
        response = client.post(
            "/api/exports/csv",
            json={
                "filename": "report.csv",
                "columns": ["note"],
                "rows": [],
            },
        )
    assert response.status_code == 500
    assert response.json() == {"detail": "The CSV could not be created. Try again."}


def test_endpoint_removes_temporary_export_after_response(client: TestClient) -> None:
    from pft.infrastructure.exporters import CsvExporter

    paths: list[Path] = []
    original = CsvExporter.export

    def record_path(self: CsvExporter, rows: object, path: Path) -> None:
        paths.append(path)
        original(self, [], path)

    with patch("pft.api.exports.CsvExporter.export", record_path):
        response = client.post(
            "/api/exports/csv",
            json={
                "filename": "report.csv",
                "columns": ["note"],
                "rows": [],
            },
        )
    assert response.status_code == 200
    assert len(paths) == 1
    assert not paths[0].parent.exists()
