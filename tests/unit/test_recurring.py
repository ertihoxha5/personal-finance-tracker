"""Recurring transactions (#25, FR-18). Synthetic data only."""

import datetime as dt
from pathlib import Path
from typing import Any, cast

import pytest

from pft.domain.category import AccountType, Category, Direction, Frequency
from pft.domain.exceptions import (
    DataImportError,
    InvalidDateError,
    InvalidTransferError,
)
from pft.domain.money import Money
from pft.domain.recurring import RecurringTransaction, occurrence_date
from pft.domain.transaction import Expense, Income, Transaction, Transfer
from pft.infrastructure.repository import RECURRING_COLUMNS, SqliteRepository
from pft.services.ledger import Ledger

D = dt.date
SEPT_1 = D(2026, 9, 1)


def rent(start: D = SEPT_1, **kwargs: Any) -> RecurringTransaction:
    template = Expense(
        id=0,
        account_id=1,
        amount=Money.of("600.00"),
        date=start,
        category=Category.RENT,
        note="Rent",
    )
    return RecurringTransaction(
        template=template,
        frequency=kwargs.pop("frequency", Frequency.MONTHLY),
        start=start,
        **kwargs,
    )


@pytest.fixture
def ledger() -> Ledger:
    ledger = Ledger()
    ledger.open_account("Checking", AccountType.BANK, Money.of("2000.00"))
    return ledger


def dates_in(ledger: Ledger) -> list[D]:
    return sorted(cast(Transaction, t).date for t in ledger.all_transactions())


# --- date logic -----------------------------------------------------------------------


def test_month_end_is_counted_from_the_start_date_not_chained() -> None:
    """31 Jan -> 28 Feb -> 31 Mar: no drift to 28 Mar after the short month."""
    starts_31_jan = [occurrence_date(Frequency.MONTHLY, D(2027, 1, 31), n) for n in range(4)]
    assert starts_31_jan == [D(2027, 1, 31), D(2027, 2, 28), D(2027, 3, 31), D(2027, 4, 30)]


def test_leap_year_february_gets_the_29th() -> None:
    assert occurrence_date(Frequency.MONTHLY, D(2028, 1, 31), 1) == D(2028, 2, 29)


def test_rule_starting_28_february_stays_on_the_28th() -> None:
    rule = rent(D(2027, 2, 28))
    assert list(rule.dates(D(2027, 5, 31))) == [
        D(2027, 2, 28),
        D(2027, 3, 28),
        D(2027, 4, 28),
        D(2027, 5, 28),
    ]


def test_rule_starting_31_march_clamps_to_30_april_then_back_to_31() -> None:
    rule = rent(D(2027, 3, 31))
    assert list(rule.dates(D(2027, 6, 30))) == [
        D(2027, 3, 31),
        D(2027, 4, 30),
        D(2027, 5, 31),
        D(2027, 6, 30),
    ]


@pytest.mark.parametrize("frequency", list(Frequency))
@pytest.mark.parametrize("start", [D(2027, 1, 31), D(2028, 2, 29), D(2026, 12, 15)])
def test_first_step_matches_frequency_next_date(frequency: Frequency, start: D) -> None:
    """The clamp is the #10 rule: one step from the start equals Frequency.next_date."""
    assert occurrence_date(frequency, start, 1) == frequency.next_date(start)


def test_weekly_and_yearly_occurrences() -> None:
    assert occurrence_date(Frequency.WEEKLY, D(2026, 12, 29), 1) == D(2027, 1, 5)
    assert occurrence_date(Frequency.YEARLY, D(2028, 2, 29), 1) == D(2029, 2, 28)
    assert occurrence_date(Frequency.YEARLY, D(2028, 2, 29), 4) == D(2032, 2, 29)


def test_dates_is_a_lazy_generator() -> None:
    from itertools import islice

    endless = rent().dates(D.max)
    assert list(islice(endless, 2)) == [D(2026, 9, 1), D(2026, 10, 1)]


# --- apply_due --------------------------------------------------------------------------


def test_monthly_rent_from_1_september_until_15_november_gives_three(ledger: Ledger) -> None:
    rule = rent()
    added = rule.apply_due(ledger, today=D(2026, 11, 15))
    assert [t.date for t in added] == [D(2026, 9, 1), D(2026, 10, 1), D(2026, 11, 1)]
    assert all(isinstance(t, Expense) and t.amount == Money.of("600.00") for t in added)
    assert len({t.id for t in added}) == 3
    assert rule.last_run == D(2026, 11, 1)
    assert ledger.account(1).balance == Money.of("200.00")


def test_running_twice_adds_nothing_new(ledger: Ledger) -> None:
    rule = rent()
    rule.apply_due(ledger, today=D(2026, 11, 15))
    assert rule.apply_due(ledger, today=D(2026, 11, 15)) == []
    assert len(dates_in(ledger)) == 3


def test_a_later_run_adds_only_the_new_month(ledger: Ledger) -> None:
    rule = rent()
    rule.apply_due(ledger, today=D(2026, 11, 15))
    added = rule.apply_due(ledger, today=D(2026, 12, 1))
    assert [t.date for t in added] == [D(2026, 12, 1)]


def test_end_date_is_respected_and_inclusive(ledger: Ledger) -> None:
    rule = rent(end=D(2026, 10, 1))
    rule.apply_due(ledger, today=D(2027, 3, 1))
    assert dates_in(ledger) == [D(2026, 9, 1), D(2026, 10, 1)]


def test_nothing_is_due_before_the_start(ledger: Ledger) -> None:
    assert rent().apply_due(ledger, today=D(2026, 8, 31)) == []


def test_restart_creates_no_duplicates(ledger: Ledger, tmp_path: Path) -> None:
    """Save the ledger and the rule row, load both as a new process would, run again."""
    repo = SqliteRepository(tmp_path / "pft.sqlite3")
    rule = rent()
    rule.apply_due(ledger, today=D(2026, 11, 15))
    repo.save(ledger)
    saved_row = rule.to_row()

    reloaded = repo.load()
    restarted = RecurringTransaction.from_row(saved_row)
    assert restarted.last_run == D(2026, 11, 1)
    assert restarted.apply_due(reloaded, today=D(2026, 11, 15)) == []
    assert len(dates_in(reloaded)) == 3


def test_lost_last_run_still_creates_no_duplicates(ledger: Ledger) -> None:
    """If last_run was not saved, items already in the account are recognised and skipped."""
    rent().apply_due(ledger, today=D(2026, 11, 15))
    forgetful = rent()  # last_run is None again
    assert forgetful.apply_due(ledger, today=D(2026, 11, 15)) == []
    assert forgetful.last_run == D(2026, 11, 1)
    assert len(dates_in(ledger)) == 3


def test_income_rule_adds_income(ledger: Ledger) -> None:
    salary = Income(
        id=0,
        account_id=1,
        amount=Money.of("2200.00"),
        date=D(2026, 10, 25),
        category=Category.SALARY,
    )
    rule = RecurringTransaction(template=salary, frequency=Frequency.MONTHLY, start=D(2026, 10, 25))
    rule.apply_due(ledger, today=D(2026, 11, 30))
    assert ledger.account(1).balance == Money.of("6400.00")


# --- validation and storage -------------------------------------------------------------


def test_transfer_template_is_rejected() -> None:
    side = Transfer(
        id=0,
        account_id=1,
        amount=Money.of("5.00"),
        date=D(2026, 9, 1),
        direction=Direction.OUT,
        transfer_id="t-1",
    )
    with pytest.raises(InvalidTransferError):
        RecurringTransaction(template=side, frequency=Frequency.MONTHLY, start=D(2026, 9, 1))


def test_end_before_start_is_rejected() -> None:
    with pytest.raises(InvalidDateError) as info:
        rent(end=D(2026, 8, 31))
    assert info.value.field == "end_date"


def test_row_round_trip_keeps_last_run_and_matches_repository_columns() -> None:
    rule = rent(end=D(2027, 8, 1), last_run=D(2026, 11, 1))
    row = rule.to_row()
    assert tuple(row) == RECURRING_COLUMNS
    assert row["last_run"] == "2026-11-01"
    assert RecurringTransaction.from_row(row) == rule


def test_bad_row_is_a_data_import_error() -> None:
    row = rent().to_row()
    del row["frequency"]
    with pytest.raises(DataImportError):
        RecurringTransaction.from_row(row)


def test_upcoming_lists_next_dates_and_stops_at_end() -> None:
    rule = rent(D(2027, 1, 31), end=D(2027, 4, 30))
    assert rule.upcoming(after=D(2027, 1, 31), limit=5) == [
        D(2027, 2, 28),
        D(2027, 3, 31),
        D(2027, 4, 30),
    ]
    assert rule.upcoming(after=D(2027, 1, 31), limit=5) == rule.upcoming(
        after=D(2027, 1, 31), limit=5
    )
