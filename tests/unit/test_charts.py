"""Optional PNG charts use report data and preserve existing files on failure."""

import datetime as dt
import importlib
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from pft.domain.category import AccountType, Category
from pft.domain.money import Money
from pft.domain.transaction import Expense, Income
from pft.infrastructure.charts import ChartUnavailableError, save_category_pie, save_monthly_trend
from pft.services.ledger import Ledger
from pft.services.reports import CategoryReport, CategoryReportData, TrendReport, TrendReportData


@pytest.fixture
def ledger() -> Ledger:
    ledger = Ledger()
    ledger.open_account("Bank", AccountType.BANK, Money.of("1000.00"))
    ledger.open_account("Savings", AccountType.SAVINGS, Money.of("100.00"))
    ledger.add_transaction(
        1,
        Income(
            id=1,
            account_id=1,
            amount=Money.of("100.10"),
            date=dt.date(2026, 10, 1),
            category=Category.SALARY,
        ),
    )
    ledger.add_transaction(
        1,
        Expense(
            id=2,
            account_id=1,
            amount=Money.of("12.50"),
            date=dt.date(2026, 11, 15),
            category=Category.FOOD,
        ),
    )
    ledger.add_transaction(
        1,
        Expense(
            id=3,
            account_id=1,
            amount=Money.of("25.00"),
            date=dt.date(2026, 11, 16),
            category=Category.TRANSPORT,
        ),
    )
    ledger.transfer(1, 2, Money.of("50.00"), dt.date(2026, 11, 17))
    return ledger


def category(ledger: Ledger) -> CategoryReportData:
    return CategoryReport(ledger, dt.date(2026, 11, 1), dt.date(2026, 11, 30)).build()


def trend(ledger: Ledger) -> TrendReportData:
    return TrendReport(ledger, 6, 2026, 11).build()


def assert_png(path: Path) -> None:
    assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    image = importlib.import_module("PIL.Image")
    with image.open(path) as picture:
        assert picture.format == "PNG"
        assert picture.size == (1200, 720)
        picture.verify()


def test_category_pie_is_a_valid_png_without_mutating_ledger(
    ledger: Ledger, tmp_path: Path
) -> None:
    pytest.importorskip("matplotlib")
    before = [t.to_row() for t in ledger.all_transactions() if isinstance(t, (Income, Expense))]
    path = tmp_path / "categories.png"
    save_category_pie(category(ledger), path)
    assert_png(path)
    assert [
        t.to_row() for t in ledger.all_transactions() if isinstance(t, (Income, Expense))
    ] == before


def test_trend_is_a_valid_png(ledger: Ledger, tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    path = tmp_path / "trend.png"
    save_monthly_trend(trend(ledger), path)
    assert_png(path)


@pytest.mark.parametrize("kind", ["category", "trend"])
def test_empty_ledger_produces_readable_png(tmp_path: Path, kind: str) -> None:
    pytest.importorskip("matplotlib")
    path = tmp_path / f"empty-{kind}.png"
    if kind == "category":
        save_category_pie(category(Ledger()), path)
    else:
        save_monthly_trend(trend(Ledger()), path)
    assert_png(path)


def test_trend_plots_exact_report_rows_in_order_including_zero_months(ledger: Ledger) -> None:
    pytest.importorskip("matplotlib")
    figure = importlib.import_module("matplotlib.figure").Figure()

    def draw_only(path: object, draw: Any) -> None:
        draw(figure)

    with patch("pft.infrastructure.charts._render", draw_only):
        save_monthly_trend(trend(ledger), "unused.png")
    lines = {
        line.get_label(): list(line.get_ydata())
        for line in figure.axes[0].lines
        if line.get_label() in {"Income", "Expenses", "Net"}
    }
    assert lines == {
        "Income": [0, 0, 0, 0, 100.10, 0],
        "Expenses": [0, 0, 0, 0, 0, 37.50],
        "Net": [0, 0, 0, 0, 100.10, -37.50],
    }
    figure.clear()


def test_pie_legend_matches_report_amounts_and_shares(ledger: Ledger) -> None:
    pytest.importorskip("matplotlib")
    figure = importlib.import_module("matplotlib.figure").Figure()

    def draw_only(path: object, draw: Any) -> None:
        draw(figure)

    with patch("pft.infrastructure.charts._render", draw_only):
        save_category_pie(category(ledger), "unused.png")
    labels = [text.get_text() for text in figure.axes[0].get_legend().get_texts()]
    assert labels == ["Transport: 25.00 (66.7%)", "Food: 12.50 (33.3%)"]
    figure.clear()


def test_missing_dependency_has_friendly_error_and_keeps_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "existing.png"
    path.write_bytes(b"previous")
    with (
        patch("pft.infrastructure.charts.importlib.import_module", side_effect=ModuleNotFoundError),
        pytest.raises(ChartUnavailableError, match="charts extra"),
    ):
        save_category_pie(category(Ledger()), path)
    assert path.read_bytes() == b"previous"


def test_render_failure_preserves_destination_and_removes_temporary_file(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    path = tmp_path / "existing.png"
    path.write_bytes(b"previous")
    with (
        patch("matplotlib.figure.Figure.savefig", side_effect=OSError("disk full")),
        pytest.raises(OSError, match="disk full"),
    ):
        save_monthly_trend(trend(Ledger()), path)
    assert path.read_bytes() == b"previous"
    assert list(tmp_path.iterdir()) == [path]


def test_invalid_extension_is_rejected_before_importing_matplotlib(tmp_path: Path) -> None:
    with (
        patch("pft.infrastructure.charts.importlib.import_module") as load,
        pytest.raises(ValueError, match=".png"),
    ):
        save_category_pie(category(Ledger()), tmp_path / "chart.svg")
    load.assert_not_called()


def test_empty_trend_report_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one month"):
        save_monthly_trend(TrendReportData(title="empty", months=()), tmp_path / "chart.png")
