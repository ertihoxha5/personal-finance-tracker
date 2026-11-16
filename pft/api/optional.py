"""Opt-in tools (#28). PFT_OPTIONAL_FEATURES=undo,import,charts enables all three.

Core routes are unchanged. History is per browser token, process-local, bounded
and reset after outside mutations. A staged history is published only after the
existing LedgerStore commits. This assumes the existing single-process API.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Any, Literal
from weakref import WeakKeyDictionary

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from pft.api.accounts import NewTransaction, NewTransfer, transaction_dto
from pft.api.reports import parse_date
from pft.api.store import LedgerStore, get_store
from pft.domain.factory import TransactionFactory
from pft.domain.transaction import Transaction
from pft.infrastructure.importer import BankCsvImporter, ImportResult
from pft.services.budget_monitor import BudgetWarning
from pft.services.commands import AddCommand, CommandError, DeleteCommand, History, TransferCommand
from pft.services.ledger import Ledger
from pft.services.reports import CategoryReport, TrendReport, parse_month

router = APIRouter(prefix="/api/optional", tags=["optional tools"])
Store = Annotated[LedgerStore, Depends(get_store)]
_LOCK = threading.Lock()
_TTL = 3600
_MAX_SESSIONS = 64


def features() -> dict[str, bool]:
    chosen = {part.strip() for part in os.environ.get("PFT_OPTIONAL_FEATURES", "").split(",")}
    return {name: name in chosen for name in ("undo", "import", "charts")}


def require(name: str) -> None:
    if not features()[name]:
        raise HTTPException(status_code=404, detail="This optional feature is disabled.")


@router.get("/features")
def capabilities() -> dict[str, bool]:
    return features()


def revision(ledger: Ledger, store: LedgerStore) -> str:
    """Detect changes made by core routes, another session or due recurring rules."""
    snapshot = {
        "accounts": [
            (a.id, a.name, a.type.value, str(a.opening_balance.amount), a.opening_balance.currency)
            for a in sorted(ledger.accounts, key=lambda a: a.id)
        ],
        "transactions": [
            t.to_row()
            for t in sorted(ledger.all_transactions(), key=lambda t: t.id)
            if isinstance(t, Transaction)
        ],
        "recurring": [r.to_row() for r in ledger.recurring],
        "budgets": [b.to_row() for b in store.budgets()],
        "ids": [ledger.next_account_id, ledger.next_transaction_id()],
    }
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


@dataclass
class Session:
    revision: str
    history: History = field(default_factory=History)
    touched: float = field(default_factory=time.monotonic)


_SESSIONS: WeakKeyDictionary[LedgerStore, dict[str, Session]] = WeakKeyDictionary()


def sessions(store: LedgerStore) -> dict[str, Session]:
    cache = _SESSIONS.setdefault(store, {})
    for token in list(cache):
        if time.monotonic() - cache[token].touched > _TTL:
            del cache[token]
    return cache


def session_for(store: LedgerStore, token: str) -> Session:
    session = sessions(store).get(token)
    if session is None:
        raise CommandError("History session expired. Start a new tools session.")
    session.touched = time.monotonic()
    return session


def history_dto(token: str, session: Session, *, reset: bool = False) -> dict[str, Any]:
    return {
        "token": token,
        "can_undo": session.history.can_undo,
        "can_redo": session.history.can_redo,
        "reset": reset,
    }


@router.post("/history")
def start_history(store: Store) -> dict[str, Any]:
    require("undo")
    with _LOCK:
        cache = sessions(store)
        if len(cache) >= _MAX_SESSIONS:
            oldest = min(cache, key=lambda token: cache[token].touched)
            del cache[oldest]
        token = uuid.uuid4().hex
        session = Session(store.read(lambda ledger: revision(ledger, store)))
        cache[token] = session
        return history_dto(token, session)


@router.get("/history/{token}")
def read_history(token: str, store: Store) -> dict[str, Any]:
    require("undo")
    with _LOCK:
        session = session_for(store, token)
        current = store.read(lambda ledger: revision(ledger, store))
        reset = current != session.revision
        if reset:
            session.revision, session.history = current, History()
        return history_dto(token, session, reset=reset)


class HistoryAction(BaseModel):
    action: Literal["add", "delete", "transfer", "undo", "redo"]
    transaction: NewTransaction | None = None
    transfer: NewTransfer | None = None
    account_id: int | None = None
    transaction_id: int | None = None


@router.post("/history/{token}")
def change_history(token: str, body: HistoryAction, store: Store) -> dict[str, Any]:
    require("undo")
    with _LOCK:
        session = session_for(store, token)
        pending: list[Session] = []
        warnings: list[BudgetWarning] = []

        def change(ledger: Ledger) -> None:
            current = revision(ledger, store)
            if current != session.revision:
                # Reject this click; require a refresh before another action.
                raise CommandError(
                    "Data changed outside this tools session. Refresh its history first."
                )
            history = session.history.fork(ledger)
            ledger.subscribe(store.budget_monitor(ledger, warnings.append))
            if body.action == "add" and body.transaction is not None:
                item = body.transaction
                row = TransactionFactory.from_input(
                    item.kind,
                    item.amount,
                    item.category,
                    item.date,
                    item.account_id,
                    item.note,
                    transaction_id=ledger.next_transaction_id(),
                )
                history.execute(AddCommand(ledger, row))
            elif (
                body.action == "delete"
                and body.account_id is not None
                and body.transaction_id is not None
            ):
                history.execute(DeleteCommand(ledger, body.account_id, body.transaction_id))
            elif body.action == "transfer" and body.transfer is not None:
                item_transfer = body.transfer
                validated = TransactionFactory.from_input(
                    "expense",
                    item_transfer.amount,
                    "other",
                    item_transfer.date,
                    item_transfer.from_account_id,
                    item_transfer.note,
                    transaction_id=0,
                )
                history.execute(
                    TransferCommand(
                        ledger,
                        item_transfer.from_account_id,
                        item_transfer.to_account_id,
                        validated.amount,
                        validated.date,
                        item_transfer.note,
                    )
                )
            elif body.action == "undo":
                history.undo()
            elif body.action == "redo":
                history.redo()
            else:
                raise CommandError("Supply the required fields for this history action.")
            pending.append(Session(revision(ledger, store), history))

        store.write(change)
        sessions(store)[token] = pending[0]  # save succeeded; now publish history
        return history_dto(token, pending[0]) | {"warnings": [w.to_dict() for w in warnings]}


class ImportRequest(BaseModel):
    account_id: int
    csv_text: str = Field(max_length=1_000_000)
    expected_revision: str | None = None


def import_dto(result: ImportResult) -> dict[str, Any]:
    return {
        "accepted": [
            {"row_number": item.row_number, "transaction": transaction_dto(item.transaction)}
            for item in result.accepted
        ],
        "errors": [
            {"row_number": issue.row_number, "reason": issue.reason, "field": issue.field}
            for issue in result.errors
        ],
    }


@router.post("/import/preview")
def preview_import(body: ImportRequest, store: Store) -> dict[str, Any]:
    require("import")

    def build(ledger: Ledger) -> dict[str, Any]:
        return import_dto(
            BankCsvImporter().preview(ledger, io.StringIO(body.csv_text), body.account_id)
        ) | {"revision": revision(ledger, store)}

    return store.read(build)


@router.post("/import/confirm")
def confirm_import(body: ImportRequest, store: Store) -> dict[str, Any]:
    require("import")

    def commit(ledger: Ledger) -> dict[str, Any]:
        if not body.expected_revision or body.expected_revision != revision(ledger, store):
            raise CommandError(
                "Data changed or preview is missing. Preview the CSV again before importing."
            )
        warnings: list[BudgetWarning] = []
        ledger.subscribe(store.budget_monitor(ledger, warnings.append))
        result = BankCsvImporter().import_stream(
            ledger, io.StringIO(body.csv_text), body.account_id
        )
        return import_dto(result) | {"warnings": [w.to_dict() for w in warnings]}

    return store.write(commit)


@router.get("/charts/{kind}")
def chart_download(
    kind: Literal["categories", "trend"],
    store: Store,
    start: str = "",
    end: str = "",
    months: Annotated[int, Query(ge=1, le=120)] = 6,
) -> Response:
    require("charts")
    from pft.infrastructure.charts import (
        ChartUnavailableError,
        save_category_pie,
        save_monthly_trend,
    )

    try:
        with TemporaryDirectory(prefix="pft-chart-download-") as directory:
            path = Path(directory) / f"{kind}.png"
            if kind == "categories":
                data = store.read(
                    lambda ledger: CategoryReport(
                        ledger, parse_date(start, "start"), parse_date(end, "end")
                    ).build()
                )
                save_category_pie(data, path)
            else:
                year, month = parse_month(end)
                trend = store.read(lambda ledger: TrendReport(ledger, months, year, month).build())
                save_monthly_trend(trend, path)
            content = path.read_bytes()
    except ChartUnavailableError as exc:
        raise HTTPException(status_code=503, detail=exc.message) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail="The PNG could not be created. Try again."
        ) from exc
    return Response(
        content=content,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{kind}.png"'},
    )
