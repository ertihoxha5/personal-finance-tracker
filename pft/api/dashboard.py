"""GET /api/dashboard?month=YYYY-MM: everything the Dashboard screen shows for one month (#19).

All numbers come from ``MonthlySummary``; React only displays them. Amounts are decimal
strings, ``savings_rate`` is a percentage string with one decimal ("25.0"), and the month
list and the default month come from the stored transactions. Transfers are left out, as in
the report. Problems use the usual ``{code, message, field}`` error shape.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from pft.api.store import LedgerStore, get_store
from pft.domain.category import Kind
from pft.domain.exceptions import InvalidDateError
from pft.domain.transaction import Transaction
from pft.services.ledger import Ledger
from pft.services.reports import MonthlySummary, PeriodTotals, previous_month

router = APIRouter(prefix="/api", tags=["dashboard"])
Store = Annotated[LedgerStore, Depends(get_store)]

TREND_MONTHS = 5
RECENT_COUNT = 8
_MONTH = re.compile(r"(\d{4})-(0[1-9]|1[0-2])")


def parse_month(text: str) -> tuple[int, int]:
    match = _MONTH.fullmatch(text.strip())
    if match is None:
        raise InvalidDateError(f"invalid month {text!r}; use the form 2026-11", field="month")
    return int(match[1]), int(match[2])


def _key(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def _totals_dto(totals: PeriodTotals) -> dict[str, Any]:
    return {
        "income": str(totals.income.amount),
        "expenses": str(totals.expenses.amount),
        "net": str(totals.net.amount),
        "savings_rate": str(totals.savings_rate),
        "transaction_count": totals.transaction_count,
    }


def _counted(ledger: Ledger) -> list[Transaction]:
    return [
        t
        for t in ledger.all_transactions()
        if isinstance(t, Transaction) and t.kind is not Kind.TRANSFER
    ]


def build_dashboard(ledger: Ledger, requested: str | None) -> dict[str, Any]:
    counted = _counted(ledger)
    months = {(t.date.year, t.date.month) for t in counted}
    if requested is not None:
        year, month = parse_month(requested)
    elif months:
        year, month = max(months)
    else:
        today = dt.date.today()
        year, month = today.year, today.month
    months.add((year, month))  # the picker always offers the month being shown

    summary = MonthlySummary(ledger, year, month).build()

    trend = []
    ty, tm = year, month
    for _ in range(TREND_MONTHS):
        totals = MonthlySummary(ledger, ty, tm).build().totals
        trend.append(
            {
                "month": _key(ty, tm),
                "income": str(totals.income.amount),
                "expenses": str(totals.expenses.amount),
            }
        )
        ty, tm = previous_month(ty, tm)
    trend.reverse()

    in_month = [t for t in counted if (t.date.year, t.date.month) == (year, month)]
    newest_first = sorted(in_month, key=lambda t: (t.date, t.id), reverse=True)
    recent = [
        {
            "id": t.id,
            "date": t.date.isoformat(),
            "note": t.note,
            "category": t.category.value,
            "kind": t.kind.value,
            "account": {"id": t.account_id, "name": ledger.account(t.account_id).name},
            "amount": str(t.amount.amount),
        }
        for t in newest_first[:RECENT_COUNT]
    ]

    return {
        "month": _key(year, month),
        "currency": summary.totals.income.currency,
        "available_months": [_key(y, m) for y, m in sorted(months)],
        "summary": _totals_dto(summary.totals),
        "previous": {"month": _key(summary.previous_year, summary.previous_month)}
        | _totals_dto(summary.previous),
        "changes": {
            "income": str(summary.income_change.amount),
            "expenses": str(summary.expenses_change.amount),
            "net": str(summary.net_change.amount),
        },
        "top_categories": [
            {"category": c.category.value, "total": str(c.total.amount)}
            for c in summary.top_categories
        ],
        "categories": [
            {"category": c.category.value, "total": str(c.total.amount)} for c in summary.categories
        ],
        "trend": trend,
        "recent_transactions": recent,
    }


@router.get("/dashboard")
def dashboard(store: Store, month: Annotated[str | None, Query()] = None) -> dict[str, Any]:
    return store.read(lambda ledger: build_dashboard(ledger, month))
