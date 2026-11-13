"""GET /api/reports/categories?start=YYYY-MM-DD&end=YYYY-MM-DD: spending per category (#26).

Everything comes from ``CategoryReport``; React only displays it. Both dates are inclusive, so
one day is ``start == end``. Amounts are decimal strings and ``percent`` is a string with one
decimal ("33.3"); the percentages add up to exactly "100.0" whenever there is any spending. A
period without spending gives a total of "0.00" and an empty list. A missing, malformed or
reversed date returns 422 with the usual ``{code, message, field}`` shape.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from pft.api.store import LedgerStore, get_store
from pft.domain.exceptions import InvalidDateError
from pft.services.ledger import Ledger
from pft.services.reports import CategoryReport

router = APIRouter(prefix="/api/reports", tags=["reports"])
Store = Annotated[LedgerStore, Depends(get_store)]

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_date(text: str, field: str) -> dt.date:
    """Read 2026-11-05 into a date; anything else is an InvalidDateError for ``field``."""
    if _ISO_DATE.fullmatch(text.strip()):
        try:
            return dt.date.fromisoformat(text.strip())
        except ValueError:
            pass  # e.g. 2026-02-30: the right shape but not a real day
    raise InvalidDateError(f"invalid date {text!r}; use the form 2026-11-05", field=field)


def build_category_report(ledger: Ledger, start: str, end: str) -> dict[str, Any]:
    report = CategoryReport(ledger, parse_date(start, "start"), parse_date(end, "end")).build()
    return {
        "start": report.start.isoformat(),
        "end": report.end.isoformat(),
        "currency": report.total.currency,
        "total": str(report.total.amount),
        "categories": [
            {
                "category": share.category.value,
                "total": str(share.total.amount),
                "percent": str(share.percent),
            }
            for share in report.categories
        ],
    }


@router.get("/categories")
def category_report(
    store: Store, start: Annotated[str, Query()], end: Annotated[str, Query()]
) -> dict[str, Any]:
    return store.read(lambda ledger: build_category_report(ledger, start, end))
