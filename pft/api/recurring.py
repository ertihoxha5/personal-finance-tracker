"""Recurring rules routes (#25, FR-18), backed by the Ledger through the LedgerStore.

Every request already applies due rules when the store loads the Ledger, so the routes
here only create, list and preview rules. Dates are ISO strings, amounts decimal strings,
and errors become {code, message, field} like every other route (see pft.api.main).
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from pft.api.accounts import _date_param, transaction_dto
from pft.api.store import LedgerStore, get_store
from pft.domain.category import Category, Frequency
from pft.domain.exceptions import InvalidDateError
from pft.domain.factory import TransactionFactory
from pft.domain.recurring import RecurringTransaction
from pft.services.ledger import Ledger

router = APIRouter(prefix="/api/recurring", tags=["recurring"])
Store = Annotated[LedgerStore, Depends(get_store)]

UPCOMING_COUNT = 3  # next dates shown for each saved rule
MAX_PREVIEW = 12  # the most dates a preview lists in each group


class NewRecurring(BaseModel):
    kind: str
    account_id: int
    amount: str
    category: str = Category.OTHER.value
    note: str = ""
    frequency: str
    start_date: str
    end_date: str | None = None


def _end(text: str | None) -> dt.date | None:
    return _date_param(text, "end_date") if text and text.strip() else None


def rule_dto(rule: RecurringTransaction, today: dt.date) -> dict[str, Any]:
    """The stored row (RECURRING_COLUMNS) plus the next dates after today."""
    row: dict[str, Any] = dict(rule.to_row())
    row["account_id"] = rule.template.account_id
    row["end_date"] = row["end_date"] or None
    row["last_run"] = row["last_run"] or None
    row["upcoming"] = [d.isoformat() for d in rule.upcoming(after=today, limit=UPCOMING_COUNT)]
    return row


@router.get("")
def list_rules(store: Store) -> list[dict[str, Any]]:
    today = store.today()
    return store.read(lambda ledger: [rule_dto(r, today) for r in ledger.recurring])


@router.post("", status_code=201)
def create_rule(body: NewRecurring, store: Store) -> dict[str, Any]:
    """Save a rule and add the occurrences that are already due (start date up to today)."""
    today = store.today()
    frequency = Frequency.from_text(body.frequency)
    start = _date_param(body.start_date, "start_date")
    end = _end(body.end_date)

    def create(ledger: Ledger) -> dict[str, Any]:
        ledger.account(body.account_id)  # an unknown account is reported before anything else
        template = TransactionFactory.from_input(
            body.kind,
            body.amount,
            body.category,
            start.isoformat(),
            body.account_id,
            body.note,
            transaction_id=0,
        )
        rule = RecurringTransaction(template=template, frequency=frequency, start=start, end=end)
        ledger.add_recurring(rule)
        added = rule.apply_due(ledger, today)
        return {"rule": rule_dto(rule, today), "added": [transaction_dto(t) for t in added]}

    return store.write(create)


@router.get("/preview")
def preview(
    store: Store,
    frequency: str,
    start_date: str,
    end_date: str | None = None,
    count: Annotated[int, Query(ge=1, le=MAX_PREVIEW)] = 6,
) -> dict[str, Any]:
    """Dates a rule would produce, without saving anything.

    ``due_now`` are the dates up to today, which saving the rule adds at once (at most
    MAX_PREVIEW are listed; ``due_count`` is the full number). ``upcoming`` are the next
    ``count`` dates after today. Month ends follow the same rule as apply_due.
    """
    freq = Frequency.from_text(frequency)
    start = _date_param(start_date, "start_date")
    end = _end(end_date)
    if end is not None and end < start:
        raise InvalidDateError("end date must be on or after the start date", field="end_date")
    today = store.today()
    # A template is needed to build the rule; its values do not affect the dates.
    template = TransactionFactory.from_input(
        "expense", "1", "other", start.isoformat(), 0, "", transaction_id=0
    )
    rule = RecurringTransaction(template=template, frequency=freq, start=start, end=end)
    due = list(rule.dates(today))
    return {
        "due_count": len(due),
        "due_now": [d.isoformat() for d in due[:MAX_PREVIEW]],
        "upcoming": [d.isoformat() for d in rule.upcoming(after=today, limit=count)],
    }
