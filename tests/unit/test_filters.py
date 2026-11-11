"""Task #08 predicates tested independently of the upcoming Transaction class."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from enum import Enum
from functools import partial
from types import GeneratorType

import pytest

from pft.domain.exceptions import CurrencyMismatchError
from pft.domain.money import Money
from pft.services.filters import (
    FilterableTransaction,
    all_of,
    amount_between,
    any_of,
    apply_filters,
    between,
    by_account,
    by_category,
    by_kind,
    month_preset,
)


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


def test_all_of_requires_every_condition() -> None:
    predicate = all_of(by_category(StubCategory.FOOD), by_account(1))
    assert predicate(StubTransaction())
    assert not predicate(StubTransaction(account_id=2))
    assert not predicate(StubTransaction(category=StubCategory.RENT))


def test_any_of_accepts_either_condition() -> None:
    predicate = any_of(by_category(StubCategory.RENT), by_account(2))
    assert predicate(StubTransaction(category=StubCategory.RENT))
    assert predicate(StubTransaction(account_id=2))
    assert not predicate(StubTransaction())


def test_empty_combinations_follow_all_and_any_semantics() -> None:
    assert all_of()(StubTransaction())
    assert not any_of()(StubTransaction())


def test_combinations_short_circuit() -> None:
    def must_not_run(transaction: FilterableTransaction) -> bool:
        raise AssertionError("short-circuited predicate was evaluated")

    assert not all_of(by_account(2), must_not_run)(StubTransaction())
    assert any_of(by_account(1), must_not_run)(StubTransaction())


def test_food_and_amount_above_twenty() -> None:
    matching = StubTransaction(amount=Money.of("20.01"))
    items = [
        StubTransaction(amount=Money.of("20.00")),
        matching,
        StubTransaction(category=StubCategory.RENT, amount=Money.of("30.00")),
    ]
    result = apply_filters(
        items,
        by_category(StubCategory.FOOD),
        amount_between(Money.of("20.01"), Money.of("100.00")),
    )
    assert list(result) == [matching]


def test_no_filters_preserves_order_identity_and_concrete_type() -> None:
    first, second = StubTransaction(account_id=2), StubTransaction(account_id=1)
    result: Iterator[StubTransaction] = apply_filters([first, second])
    assert next(result) is first
    assert next(result) is second
    assert list(result) == []


def test_result_is_a_lazy_single_pass_generator() -> None:
    consumed: list[int] = []
    evaluated: list[int] = []

    def source() -> Iterator[StubTransaction]:
        for account_id in (1, 2, 3):
            consumed.append(account_id)
            yield StubTransaction(account_id=account_id)

    def matches(transaction: FilterableTransaction) -> bool:
        evaluated.append(transaction.account_id)
        return transaction.account_id >= 2

    result = apply_filters(source(), matches)
    assert isinstance(result, GeneratorType)
    assert consumed == evaluated == []
    assert next(result).account_id == 2
    assert consumed == evaluated == [1, 2]
    assert [transaction.account_id for transaction in result] == [3]
    assert consumed == evaluated == [1, 2, 3]
    assert list(result) == []


def test_nested_combinations_and_empty_source() -> None:
    predicate = all_of(by_kind(StubKind.EXPENSE), any_of(by_account(1), by_account(2)))
    assert predicate(StubTransaction(account_id=2))
    assert not predicate(StubTransaction(account_id=3))
    assert list(apply_filters([], predicate)) == []


@pytest.mark.parametrize("year, month, last_day", [(2024, 2, 29), (2026, 2, 28), (2026, 12, 31)])
def test_month_preset_binds_calendar_boundaries(year: int, month: int, last_day: int) -> None:
    preset = month_preset(year, month)
    assert isinstance(preset, partial)
    predicate = preset()
    assert predicate(StubTransaction(date=date(year, month, 1)))
    assert predicate(StubTransaction(date=date(year, month, last_day)))
    outside = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    assert not predicate(StubTransaction(date=outside))


def test_invalid_month_preset_is_rejected() -> None:
    with pytest.raises(ValueError):
        month_preset(2026, 13)
