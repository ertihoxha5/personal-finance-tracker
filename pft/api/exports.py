"""CSV downloads of the current frontend preview snapshot for task #16."""

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field, model_validator

from pft.infrastructure.exporters import CsvExporter, Exporter, MarkdownExporter

router = APIRouter(prefix="/api/exports", tags=["exports"])
FILENAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._ -]*\.csv$"


class CsvDownloadRequest(BaseModel):
    """Rows and selection metadata captured when the user clicks Download."""

    filename: str = Field(pattern=FILENAME_PATTERN, max_length=100)
    columns: list[str] = Field(min_length=1, max_length=30)
    rows: list[dict[str, str | int | None]] = Field(max_length=10_000)
    filters: dict[str, str | list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_columns(self) -> "CsvDownloadRequest":
        """Reject malformed schemas before the export writes a file."""
        if any(not column.strip() for column in self.columns):
            raise ValueError("column names must not be blank")
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("column names must be unique")
        allowed = set(self.columns)
        if any(set(row) - allowed for row in self.rows):
            raise ValueError("row keys must match the requested columns")
        return self


@router.post("/csv")
def download_csv(payload: CsvDownloadRequest) -> Response:
    """Export an already selected preview snapshot and discard temporary files.

    Rows arrive in the visible sort order. Selection metadata accompanies the
    snapshot for future repository-backed export integration. This endpoint
    serializes the supplied snapshot and does not query the database.
    """
    try:
        with TemporaryDirectory(prefix="pft-download-") as directory:
            path = Path(directory) / "export.csv"
            CsvExporter(fieldnames=payload.columns).export(payload.rows, path)
            content = path.read_bytes()
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail="The CSV could not be created. Try again."
        ) from exc
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload.filename}"'},
    )


class TextDownloadRequest(CsvDownloadRequest):
    """The same snapshot contract for the two approved text formats."""

    filename: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._ -]*\.(json|md)$", max_length=100)


@router.post("/{fmt}")
def download_text(fmt: str, payload: TextDownloadRequest) -> Response:
    if fmt not in {"json", "md"}:
        raise HTTPException(status_code=404, detail="Unsupported export format.")
    if not payload.filename.endswith(f".{fmt}"):
        raise HTTPException(status_code=422, detail="Filename must match the selected format.")
    exporter = Exporter.for_format(fmt)
    if isinstance(exporter, MarkdownExporter):
        exporter.fieldnames = tuple(payload.columns)
    # Keep the requested column order, including missing cells and empty reports.
    rows = [{column: row.get(column) for column in payload.columns} for row in payload.rows]
    try:
        with TemporaryDirectory(prefix="pft-download-") as directory:
            path = Path(directory) / f"export.{fmt}"
            exporter.export(rows, path)
            content = path.read_bytes()
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail="The export could not be created. Try again."
        ) from exc
    return Response(
        content=content,
        media_type="application/json" if fmt == "json" else "text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload.filename}"'},
    )
