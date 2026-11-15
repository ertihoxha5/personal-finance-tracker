"""Optional matplotlib PNG charts (#28); reporting owns all financial arithmetic.

Matplotlib is imported only when rendering. Use ``pip install -e '.[charts]'``
to enable this module; importing the core application never needs matplotlib.
Float conversion is confined to drawing coordinates, never report calculations.
"""

from __future__ import annotations

import importlib
import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pft.domain.exceptions import FinanceError
from pft.services.reports import CategoryReportData, TrendReportData

_RENDER_LOCK = threading.Lock()  # matplotlib rendering uses shared caches
_COLORS = (
    "#2563eb",
    "#d97706",
    "#059669",
    "#9333ea",
    "#dc2626",
    "#0891b2",
    "#4f46e5",
    "#be185d",
    "#64748b",
)


class ChartUnavailableError(FinanceError):
    """The optional chart dependency has not been installed."""

    code = "chart_unavailable"


def _render(path: str | Path, draw: Callable[[Any], None]) -> None:
    destination = Path(path)
    if destination.suffix.lower() != ".png":
        raise ValueError("Chart filename must end in .png")
    with _RENDER_LOCK:
        try:
            figure_type = importlib.import_module("matplotlib.figure").Figure
            canvas_type = importlib.import_module("matplotlib.backends.backend_agg").FigureCanvasAgg
        except ModuleNotFoundError as exc:
            raise ChartUnavailableError(
                "PNG charts require the optional charts extra: pip install -e '.[charts]'"
            ) from exc
        figure = figure_type(figsize=(10, 6), dpi=120, layout="constrained")
        canvas_type(figure)
        pending: Path | None = None
        try:
            draw(figure)
            with tempfile.NamedTemporaryFile(
                dir=destination.parent,
                prefix=".pft-chart-",
                suffix=".tmp",
                delete=False,
            ) as stream:
                pending = Path(stream.name)
                figure.savefig(stream, format="png", facecolor="white")
            os.replace(pending, destination)
        finally:
            figure.clear()
            if pending is not None:
                pending.unlink(missing_ok=True)


def save_category_pie(report: CategoryReportData, path: str | Path) -> None:
    """Save category spending as a pie with a readable amount/percentage legend."""

    def draw(figure: Any) -> None:
        axis = figure.subplots()
        axis.set_title("Spending by category", fontsize=18, pad=20)
        figure.supxlabel(
            f"{report.start.isoformat()} to {report.end.isoformat()} | {report.total.currency}"
        )
        if not report.categories:
            axis.text(0.5, 0.5, "No expenses in this period", ha="center", va="center", fontsize=16)
            axis.set_axis_off()
            return
        wedges, _ = axis.pie(
            [float(item.total.amount) for item in report.categories],
            colors=_COLORS,
            startangle=90,
            counterclock=False,
            wedgeprops={"edgecolor": "white", "linewidth": 2},
        )
        labels = [
            f"{item.category.value.replace('_', ' ').title()}: "
            f"{item.total.amount:,.2f} ({item.percent}%)"
            for item in report.categories
        ]
        axis.legend(wedges, labels, loc="center left", bbox_to_anchor=(1, 0.5), frameon=False)
        axis.set_aspect("equal")

    _render(path, draw)


def save_monthly_trend(report: TrendReportData, path: str | Path) -> None:
    """Save income, expenses and net for every month, including zero-filled months."""
    if not report.months:
        raise ValueError("A trend chart requires at least one month")

    def draw(figure: Any) -> None:
        axis = figure.subplots()
        labels = [f"{row.year:04d}-{row.month:02d}" for row in report.months]
        x = list(range(len(labels)))
        for field, label, color, style in (
            ("income", "Income", "#059669", "-"),
            ("expenses", "Expenses", "#d97706", "--"),
            ("net", "Net", "#2563eb", ":"),
        ):
            axis.plot(
                x,
                [float(getattr(row, field).amount) for row in report.months],
                label=label,
                color=color,
                linestyle=style,
                marker="o",
                markersize=4,
            )
        step = max(1, (len(labels) + 11) // 12)
        ticks = sorted(set([*range(0, len(labels), step), len(labels) - 1]))
        axis.set_xticks(ticks, [labels[i] for i in ticks], rotation=35, ha="right")
        axis.set_title("Monthly income, expenses and net", fontsize=18, pad=16)
        axis.set_ylabel(report.months[0].income.currency)
        axis.grid(axis="y", alpha=0.25)
        axis.axhline(0, color="#64748b", linewidth=0.8)
        axis.legend(frameon=False, loc="best")
        axis.spines[["top", "right"]].set_visible(False)

    _render(path, draw)
