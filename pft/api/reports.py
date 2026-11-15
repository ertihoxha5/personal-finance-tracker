"""GET /api/reports/categories?start=YYYY-MM-DD&end=YYYY-MM-DD: spending per category (#26).

Everything comes from ``CategoryReport``; React only displays it. Both dates are inclusive, so
one day is ``start == end``. Amounts are decimal strings and ``percent`` is a string with one
decimal ("33.3"); the percentages add up to exactly "100.0" whenever there is any spending. A
period without spending gives a total of "0.00" and an empty list. A missing, malformed or
reversed date returns 422 with the usual ``{code, message, field}`` shape.

GET /api/reports/budget?month=YYYY-MM (#31): planned versus actual for the budgets of one month
(default: the current month), from ``BudgetReport``. Each row has ``planned``, ``actual`` and
``difference`` (planned minus actual, negative when overspent) as decimal strings,
``usage_percent`` and a ``status`` of "ok", "warning" or "over". A month without budgets gives
an empty ``rows`` list and zero totals.

GET /api/reports/trend?months=6&end=YYYY-MM (#31): income, expenses and net for each of the
last ``months`` months up to ``end`` (default: the current month), from ``TrendReport``.
Always exactly ``months`` rows, oldest first; a month without data shows "0.00".
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from pft.api.store import LedgerStore, get_store
from pft.domain.budget import Budget
from pft.domain.exceptions import InvalidDateError
from pft.services.ledger import Ledger
from pft.services.reports import (
    MAX_TREND_MONTHS,
    BudgetReport,
    CategoryReport,
    TrendReport,
    parse_month,
)

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


def build_budget_report(ledger: Ledger, budgets: list[Budget], month: str) -> dict[str, Any]:
    report = BudgetReport(ledger, budgets, month).build()
    return {
        "month": report.month,
        "currency": report.planned.currency,
        "rows": [
            {
                "category": line.category.value,
                "planned": str(line.planned.amount),
                "actual": str(line.actual.amount),
                "difference": str(line.difference.amount),
                "usage_percent": str(line.usage),
                "status": line.status.value,
            }
            for line in report.lines
        ],
        "totals": {
            "planned": str(report.planned.amount),
            "actual": str(report.actual.amount),
            "difference": str(report.difference.amount),
        },
    }


def build_trend_report(ledger: Ledger, months: int, end: str) -> dict[str, Any]:
    year, month = parse_month(end)
    report = TrendReport(ledger, months, year, month).build()
    return {
        "months": [
            {
                "month": f"{row.year}-{row.month:02d}",
                "income": str(row.income.amount),
                "expenses": str(row.expenses.amount),
                "net": str(row.net.amount),
            }
            for row in report.months
        ],
    }


@router.get("/budget")
def budget_report(store: Store, month: Annotated[str | None, Query()] = None) -> dict[str, Any]:
    chosen = month if month else store.today().strftime("%Y-%m")
    return store.read(lambda ledger: build_budget_report(ledger, store.budgets(), chosen))


@router.get("/trend")
def trend_report(
    store: Store,
    months: Annotated[int, Query(ge=1, le=MAX_TREND_MONTHS)] = 6,
    end: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    chosen = end if end else store.today().strftime("%Y-%m")
    try:
        return store.read(lambda ledger: build_trend_report(ledger, months, chosen))
    except InvalidDateError as exc:  # the month checks name the field "month"; here it is "end"
        raise InvalidDateError(exc.message, field="end") from exc
