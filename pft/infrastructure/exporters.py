"""Export strategies registered by format name for task #16."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from enum import Enum
from functools import singledispatch
from itertools import chain
from pathlib import Path
from typing import ClassVar

from pft.domain.money import Money
from pft.domain.transaction import CSV_COLUMNS

ExportRow = Mapping[str, object]


@singledispatch
def format_value(value: object) -> str:
    """Render an export cell, keeping None empty and other values as text."""
    return "" if value is None else str(value)


@format_value.register
def _format_money(value: Money) -> str:
    return str(value.amount)


@format_value.register
def _format_date(value: date) -> str:
    return value.isoformat()


@format_value.register
def _format_enum(value: Enum) -> str:
    return value.name


class Exporter(ABC):
    """Common interface for file exporters that register through subclass creation."""

    registry: ClassVar[dict[str, type[Exporter]]] = {}

    def __init_subclass__(cls, *, fmt: str = "", **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if fmt:
            name = fmt.strip().lower()
            if not name:
                raise ValueError("export format must not be blank")
            if name in Exporter.registry:
                raise ValueError(f"export format {name!r} is already registered")
            Exporter.registry[name] = cls

    @classmethod
    def for_format(cls, fmt: str) -> Exporter:
        """Build the registered exporter, or list the known formats in an error."""
        name = fmt.strip().lower()
        try:
            exporter_type = cls.registry[name]
        except KeyError:
            known = ", ".join(sorted(cls.registry))
            raise ValueError(f"unknown export format {fmt!r}; known formats: {known}") from None
        return exporter_type()

    @abstractmethod
    def export(self, rows: Iterable[ExportRow], path: str | Path) -> None:
        """Write rows to path, raising an exception if the export fails."""


class CsvExporter(Exporter, fmt="csv"):
    """Write quoted UTF-8 CSV with a header and Windows-friendly line endings.

    Column order follows the first row. Explicit fieldnames support report
    schemas and empty reports. Empty input defaults to the transaction schema.
    A UTF-8 BOM lets Excel detect accents and the euro sign on direct opening.
    The destination is replaced only after every row has been written, so a
    failing generator or invalid row leaves an existing export intact.
    """

    def __init__(self, fieldnames: Sequence[str] | None = None) -> None:
        self.fieldnames = tuple(fieldnames) if fieldnames is not None else None

    def export(self, rows: Iterable[ExportRow], path: str | Path) -> None:
        destination = Path(path)
        iterator = iter(rows)
        first = next(iterator, None)
        fields = self.fieldnames
        if fields is None:
            fields = tuple(first) if first is not None else CSV_COLUMNS
        if not fields or len(set(fields)) != len(fields):
            raise ValueError("CSV columns must be nonempty and unique")

        pending_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8-sig",
                newline="",
                dir=destination.parent,
                prefix=".pft-export-",
                suffix=".tmp",
                delete=False,
            ) as stream:
                pending_path = Path(stream.name)
                writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\r\n")
                writer.writeheader()
                pending_rows = iterator if first is None else chain((first,), iterator)
                for row in pending_rows:
                    writer.writerow({key: format_value(value) for key, value in row.items()})
            os.replace(pending_path, destination)
        finally:
            if pending_path is not None:
                pending_path.unlink(missing_ok=True)


def _write_text_export(path: str | Path, content: str) -> None:
    """Replace a text export only after its complete content is written."""
    destination = Path(path)
    pending_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=destination.parent,
            prefix=".pft-export-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            pending_path = Path(stream.name)
            stream.write(content)
        os.replace(pending_path, destination)
    finally:
        if pending_path is not None:
            pending_path.unlink(missing_ok=True)


class JsonExporter(Exporter, fmt="json"):
    """Export rows as indented JSON; Money uses exact decimal text."""

    def export(self, rows: Iterable[ExportRow], path: str | Path) -> None:
        content = json.dumps(
            [
                {
                    key: format_value(value) if isinstance(value, (Money, date, Enum)) else value
                    for key, value in row.items()
                }
                for row in rows
            ],
            indent=2,
            ensure_ascii=False,
            default=format_value,
        )
        _write_text_export(path, content + "\n")


def _markdown_cell(value: object) -> str:
    """Keep literal text inside one Markdown table cell."""
    return (
        format_value(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "<br>")
    )


class MarkdownExporter(Exporter, fmt="md"):
    """Export a Markdown table with first-row or explicit column order."""

    def __init__(self, fieldnames: Sequence[str] | None = None) -> None:
        self.fieldnames = tuple(fieldnames) if fieldnames is not None else None

    def export(self, rows: Iterable[ExportRow], path: str | Path) -> None:
        iterator = iter(rows)
        first = next(iterator, None)
        fields = self.fieldnames
        if fields is None:
            fields = tuple(first) if first is not None else CSV_COLUMNS
        if not fields or len(set(fields)) != len(fields):
            raise ValueError("Markdown columns must be nonempty and unique")
        lines = [
            "| " + " | ".join(_markdown_cell(field) for field in fields) + " |",
            "| " + " | ".join("---" for _ in fields) + " |",
        ]
        for row in iterator if first is None else chain((first,), iterator):
            if set(row) - set(fields):
                raise ValueError("row contains fields not in fieldnames")
            lines.append("| " + " | ".join(_markdown_cell(row.get(f)) for f in fields) + " |")
        _write_text_export(path, "\n".join(lines) + "\n")
