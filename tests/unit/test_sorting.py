"""Task #15 sorting and search with the real #14 transaction classes."""

from datetime import date

import pytest

from pft.domain.category import Category
from pft.domain.exceptions import CurrencyMismatchError
from pft.domain.money import Money
from pft.domain.transaction import Expense, Income, Transaction
from pft.services.filters import apply_filters, by_category, sort_transactions, text_contains


def examples() -> list[Transaction]:
    return [
        Expense(
            id=1,
            account_id=1,
            amount=Money.of("25.00"),
            date=date(2026, 11, 15),
            category=Category.FOOD,
            note="Lunch with team",
        ),
        Income(
            id=2,
            account_id=1,
            amount=Money.of("100.00"),
            date=date(2026, 11, 1),
            category=Category.SALARY,
            note="Monthly salary",
        ),
        Expense(
            id=3,
            account_id=1,
            amount=Money.of("9.99"),
            date=date(2026, 11, 15),
            category=Category.FOOD,
            note="Late lunch",
        ),
    ]


@pytest.mark.parametrize(
    "key, reverse, expected",
    [
        ("date", False, [2, 1, 3]),
        ("date", True, [1, 3, 2]),
        ("amount", False, [3, 1, 2]),
        ("amount", True, [2, 1, 3]),
        ("category", False, [1, 3, 2]),
        ("category", True, [2, 1, 3]),
    ],
)
def test_sort_order_and_stable_ties(key: str, reverse: bool, expected: list[int]) -> None:
    assert [item.id for item in sort_transactions(examples(), key, reverse)] == expected


def test_sort_preserves_source_order_and_object_identity() -> None:
    items = examples()
    original = list(items)
    result = sort_transactions(items)
    assert items == original
    assert result is not items
    assert result[0] is items[1]


def test_equal_amounts_keep_order_when_descending() -> None:
    items = examples()
    items[2].amount = items[0].amount
    assert [item.id for item in sort_transactions(items, "amount", True)] == [2, 1, 3]


@pytest.mark.parametrize("key", ["note", "DATE", "", "__class__"])
def test_invalid_sort_key_lists_valid_choices_even_for_empty_input(key: str) -> None:
    with pytest.raises(ValueError, match="choose one of: date, amount, category"):
        sort_transactions([], key)


def test_note_search_combines_with_filters_and_sorting() -> None:
    selected = apply_filters(examples(), by_category(Category.FOOD), text_contains("  LUNCH  "))
    assert [item.id for item in sort_transactions(selected, "amount")] == [3, 1]


def test_note_search_ignores_case_and_does_not_search_category() -> None:
    assert [item.id for item in apply_filters(examples(), text_contains("lunch"))] == [1, 3]
    assert list(apply_filters(examples(), text_contains("food"))) == []


@pytest.mark.parametrize("query", ["", "  ", "\t\n"])
def test_blank_search_returns_all_items(query: str) -> None:
    items = examples()
    assert list(apply_filters(items, text_contains(query))) == items


def test_search_supports_unicode_and_empty_notes() -> None:
    item = examples()[0]
    item.note = "Straße"
    assert text_contains("STRASSE")(item)
    item.note = ""
    assert not text_contains("lunch")(item)
    assert text_contains("")(item)


def test_empty_and_single_item_sorting() -> None:
    assert sort_transactions([]) == []
    item = examples()[0]
    assert sort_transactions(iter([item])) == [item]


def test_amount_sort_rejects_mixed_currencies() -> None:
    items = examples()
    items[0].amount = Money.of("25.00", "USD")
    with pytest.raises(CurrencyMismatchError):
        sort_transactions(items, "amount")
