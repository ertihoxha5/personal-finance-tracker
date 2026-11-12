import json
from datetime import date

import pytest

from pft.domain.category import AccountType, Category, Direction, Frequency, Kind
from pft.domain.exceptions import FinanceError, InvalidCategoryError, InvalidChoiceError

# --- Done-when checks (#10) -------------------------------------------------


def test_from_text_food_returns_food() -> None:
    assert Category.from_text("food") is Category.FOOD


def test_unknown_category_message_lists_all_values() -> None:
    with pytest.raises(InvalidCategoryError) as caught:
        Category.from_text("groceries")
    message = str(caught.value)
    assert "groceries" in message
    for category in Category:
        assert category.value in message


def test_monthly_after_31_jan_2027_is_28_feb_2027() -> None:
    assert Frequency.MONTHLY.next_date(date(2027, 1, 31)) == date(2027, 2, 28)


# --- Parsing ----------------------------------------------------------------


@pytest.mark.parametrize("text", ["  FOOD ", "Food", "fOoD", "\tfood\n"])
def test_from_text_ignores_case_and_surrounding_whitespace(text: str) -> None:
    assert Category.from_text(text) is Category.FOOD


@pytest.mark.parametrize("text", ["", "   ", "fo od", "foods"])
def test_from_text_rejects_near_misses(text: str) -> None:
    with pytest.raises(InvalidCategoryError):
        Category.from_text(text)


def test_from_text_rejects_non_strings_with_a_finance_error() -> None:
    with pytest.raises(InvalidCategoryError):
        Category.from_text(None)  # type: ignore[arg-type]


def test_unknown_category_error_targets_the_category_field() -> None:
    with pytest.raises(InvalidCategoryError) as caught:
        Category.from_text("x")
    assert caught.value.to_dict()["field"] == "category"
    assert caught.value.to_dict()["code"] == "invalid_category"


def test_kind_and_account_type_parse_the_same_way() -> None:
    assert Kind.from_text(" Expense ") is Kind.EXPENSE
    assert AccountType.from_text("BANK") is AccountType.BANK
    assert Frequency.from_text("Monthly") is Frequency.MONTHLY


def test_unknown_kind_lists_kinds_and_is_not_a_category_error() -> None:
    with pytest.raises(InvalidChoiceError) as caught:
        Kind.from_text("refund")
    assert not isinstance(caught.value, InvalidCategoryError)
    assert "income, expense, transfer" in str(caught.value)
    assert caught.value.field == "kind"


def test_unknown_account_type_targets_the_type_field() -> None:
    with pytest.raises(InvalidChoiceError) as caught:
        AccountType.from_text("crypto")
    assert caught.value.field == "type"


def test_direction_from_text() -> None:
    assert Direction.from_text(" OUT ") is Direction.OUT
    with pytest.raises(InvalidChoiceError) as caught:
        Direction.from_text("sideways")
    assert caught.value.field == "direction"


# --- Values -----------------------------------------------------------------


def test_enum_sizes_match_the_plan() -> None:
    assert (len(Category), len(Kind), len(AccountType), len(Frequency)) == (9, 3, 4, 3)


@pytest.mark.parametrize("member", [*Category, *Kind, *Direction, *AccountType, *Frequency])
def test_values_are_lowercase_names_and_round_trip_through_str(member: Category) -> None:
    assert member.value == member.name.lower()
    assert str(member) == member.value
    assert type(member)(str(member)) is member


def test_members_serialise_to_json_as_plain_strings() -> None:
    assert json.dumps({"category": Category.FOOD}) == '{"category": "food"}'


# --- Frequency.next_date ----------------------------------------------------


@pytest.mark.parametrize(
    ("frequency", "start", "expected"),
    [
        (Frequency.WEEKLY, date(2026, 11, 28), date(2026, 12, 5)),  # across a month end
        (Frequency.WEEKLY, date(2026, 12, 29), date(2027, 1, 5)),  # across a year end
        (Frequency.MONTHLY, date(2026, 11, 15), date(2026, 12, 15)),
        (Frequency.MONTHLY, date(2026, 12, 31), date(2027, 1, 31)),  # Dec -> Jan rollover
        (Frequency.MONTHLY, date(2028, 1, 31), date(2028, 2, 29)),  # leap year
        (Frequency.MONTHLY, date(2027, 3, 31), date(2027, 4, 30)),
        (Frequency.YEARLY, date(2026, 11, 12), date(2027, 11, 12)),
        (Frequency.YEARLY, date(2028, 2, 29), date(2029, 2, 28)),  # no 29 Feb in 2029
        (Frequency.YEARLY, date(2027, 2, 28), date(2028, 2, 28)),
    ],
)
def test_next_date(frequency: Frequency, start: date, expected: date) -> None:
    assert frequency.next_date(start) == expected


def test_chained_monthly_dates_drift_after_a_short_month() -> None:
    """Documents why recurring items must count from the original start date."""
    feb = Frequency.MONTHLY.next_date(date(2027, 1, 31))
    assert Frequency.MONTHLY.next_date(feb) == date(2027, 3, 28)


def test_errors_from_enums_are_finance_errors() -> None:
    with pytest.raises(FinanceError):
        Frequency.from_text("daily")
