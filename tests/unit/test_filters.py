"""Task #08 predicates tested independently of the upcoming Transaction class."""

from dataclasses import dataclass
from datetime import date
from enum import Enum

import pytest

from pft.domain.exceptions import CurrencyMismatchError
from pft.domain.money import Money
from pft.services.filters import amount_between, between, by_account, by_category, by_kind


class StubCategory(Enum):
    FOOD = "food"
    RENT = "rent"


class StubKind(Enum):
    INCOME = "income"
    EXPENSE = "expense"


@dataclass(frozen=True)
class StubTransaction:
    category: StubCategory = StubCategory.FOOD
    kind: StubKind = StubKind.EXPENSE
    account_id: int = 1
    date: date = date(2026, 11, 15)
    amount: Money = Money.of("25.00")


def test_category_matches_any_selected_category() -> None:
    predicate = by_category(StubCategory.FOOD, StubCategory.RENT)
    assert predicate(StubTransaction())
    assert predicate(StubTransaction(category=StubCategory.RENT))


def test_category_rejects_unselected_and_empty_selection() -> None:
    assert not by_category(StubCategory.RENT)(StubTransaction())
    assert not by_category()(StubTransaction())


def test_kind_matches_only_selected_kind() -> None:
    predicate = by_kind(StubKind.EXPENSE)
    assert predicate(StubTransaction())
    assert not predicate(StubTransaction(kind=StubKind.INCOME))


def test_account_matches_stable_id() -> None:
    assert by_account(1)(StubTransaction())
    assert not by_account(2)(StubTransaction())


@pytest.mark.parametrize("day, expected", [(1, True), (15, True), (30, True)])
def test_date_range_includes_both_endpoints(day: int, expected: bool) -> None:
    predicate = between(date(2026, 11, 1), date(2026, 11, 30))
    assert predicate(StubTransaction(date=date(2026, 11, day))) is expected


@pytest.mark.parametrize("day", [date(2026, 10, 31), date(2026, 12, 1)])
def test_date_range_excludes_outside_dates(day: date) -> None:
    assert not between(date(2026, 11, 1), date(2026, 11, 30))(StubTransaction(date=day))


def test_same_day_range() -> None:
    day = date(2026, 11, 15)
    assert between(day, day)(StubTransaction())


def test_reversed_date_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="start date"):
        between(date(2026, 12, 1), date(2026, 11, 1))


@pytest.mark.parametrize(
    "amount, expected",
    [("19.99", False), ("20.00", True), ("25.00", True), ("30.00", True), ("30.01", False)],
)
def test_amount_range_is_inclusive(amount: str, expected: bool) -> None:
    predicate = amount_between(Money.of("20.00"), Money.of("30.00"))
    assert predicate(StubTransaction(amount=Money.of(amount))) is expected


def test_equal_amount_bounds() -> None:
    assert amount_between(Money.of("25.00"), Money.of("25.00"))(StubTransaction())


def test_reversed_amount_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="minimum amount"):
        amount_between(Money.of("30.00"), Money.of("20.00"))


def test_amount_bounds_must_share_currency() -> None:
    with pytest.raises(CurrencyMismatchError):
        amount_between(Money.of("20.00"), Money.of("30.00", "USD"))


def test_transaction_currency_must_match_bounds() -> None:
    predicate = amount_between(Money.of("20.00"), Money.of("30.00"))
    with pytest.raises(CurrencyMismatchError):
        predicate(StubTransaction(amount=Money.of("25.00", "USD")))
