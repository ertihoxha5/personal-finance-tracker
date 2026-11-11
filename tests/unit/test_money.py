from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from pft.domain.exceptions import (
    CurrencyMismatchError,
    FinanceError,
    InvalidAmountError,
    InvalidCurrencyError,
)
from pft.domain.money import Money

# --- Done-when tests -------------------------------------------------------


def test_decimal_addition_is_exact() -> None:
    assert Money.of("0.10") + Money.of("0.20") == Money.of("0.30")


def test_rounds_half_up_to_cents() -> None:
    # As a float, 2.675 is 2.67499999... and would round down to 2.67.
    assert Money.of("2.675").amount == Decimal("2.68")


def test_float_is_rejected() -> None:
    with pytest.raises(InvalidAmountError):
        Money(0.1)  # type: ignore[arg-type]


def test_cross_currency_addition_raises() -> None:
    with pytest.raises(CurrencyMismatchError):
        Money.of("1.00", "EUR") + Money.of("1.00", "USD")


def test_is_immutable() -> None:
    money = Money.of("5.00")
    with pytest.raises(FrozenInstanceError):
        money.amount = Decimal("6.00")  # type: ignore[misc]


def test_sum_with_and_without_start_value() -> None:
    items = [Money.of("1.10"), Money.of("2.20"), Money.of("3.30")]
    assert sum(items) == Money.of("6.60")
    assert sum(items, Money.zero()) == Money.of("6.60")
    assert sum([], Money.zero()) == Money.zero()


# --- Construction edge cases -----------------------------------------------


@pytest.mark.parametrize(
    "value",
    [True, False, "abc", "", "NaN", "sNaN", "Infinity", "-Infinity", "1_000", [1], None],
)
def test_invalid_amounts_are_rejected(value: object) -> None:
    with pytest.raises(InvalidAmountError):
        Money(value)  # type: ignore[arg-type]


def test_amount_too_large_to_round_is_rejected() -> None:
    with pytest.raises(InvalidAmountError):
        Money.of("1e30")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (12, "12.00"),
        ("12.5", "12.50"),
        (" 7.1 ", "7.10"),
        (Decimal("3.14159"), "3.14"),
        ("-4.005", "-4.01"),
    ],
)
def test_valid_amounts_are_normalised(value: Decimal | int | str, expected: str) -> None:
    assert Money.of(value).amount == Decimal(expected)


def test_negative_amounts_are_allowed() -> None:
    assert Money.of("-12.50").amount == Decimal("-12.50")


@pytest.mark.parametrize("currency", ["eur", "EURO", "", "E1R", 978])
def test_invalid_currency_is_rejected(currency: object) -> None:
    with pytest.raises(InvalidCurrencyError):
        Money(Decimal(1), currency)  # type: ignore[arg-type]


def test_domain_errors_share_a_base_class() -> None:
    for error in (InvalidAmountError, InvalidCurrencyError, CurrencyMismatchError):
        assert issubclass(error, FinanceError)


# --- Arithmetic --------------------------------------------------------------


def test_subtraction() -> None:
    assert Money.of("10.00") - Money.of("2.50") == Money.of("7.50")


def test_subtraction_across_currencies_raises() -> None:
    with pytest.raises(CurrencyMismatchError):
        Money.of("1.00") - Money.of("1.00", "USD")


def test_unary_minus() -> None:
    assert -Money.of("12.50") == Money.of("-12.50")
    assert str(-Money.zero()) == "0.00 EUR"


def test_multiplication_by_int_and_decimal() -> None:
    assert Money.of("2.50") * 3 == Money.of("7.50")
    assert 3 * Money.of("2.50") == Money.of("7.50")
    assert Money.of("10.00") * Decimal("0.333") == Money.of("3.33")


def test_negative_zero_is_normalised() -> None:
    assert str(Money.zero() * -1) == "0.00 EUR"


@pytest.mark.parametrize("factor", [Money.of("2.00"), 1.5, True, "2"])
def test_invalid_multiplication_raises_type_error(factor: object) -> None:
    with pytest.raises(TypeError):
        Money.of("2.00") * factor  # type: ignore[operator]


def test_adding_a_non_money_raises_type_error() -> None:
    with pytest.raises(TypeError):
        Money.of("1.00") + 1  # type: ignore[operator]
    with pytest.raises(TypeError):
        1 + Money.of("1.00")
    with pytest.raises(TypeError):
        Money.of("1.00") - 1  # type: ignore[operator]


# --- Comparison and display --------------------------------------------------


def test_ordering_within_a_currency() -> None:
    small, big = Money.of("1.00"), Money.of("2.00")
    assert small < big
    assert big > small
    assert small <= Money.of("1.00")
    assert sorted([big, small]) == [small, big]


def test_ordering_across_currencies_raises() -> None:
    with pytest.raises(CurrencyMismatchError):
        _ = Money.of("1.00") < Money.of("2.00", "USD")


def test_ordering_against_non_money_raises_type_error() -> None:
    with pytest.raises(TypeError):
        _ = Money.of("1.00") < 2  # type: ignore[operator]


def test_equality_across_currencies_is_false_not_an_error() -> None:
    assert Money.of("1.00", "EUR") != Money.of("1.00", "USD")
    assert Money.of("1.00") != "1.00"  # type: ignore[comparison-overlap]


def test_equal_values_are_interchangeable() -> None:
    assert Money.of(1) == Money.of("1.00")
    assert hash(Money.of(1)) == hash(Money.of("1.00"))
    assert len({Money.of(1), Money.of("1.0"), Money.of("1.00")}) == 1


def test_str_format() -> None:
    assert str(Money.of("12.5")) == "12.50 EUR"
    assert str(Money.of("-3", "USD")) == "-3.00 USD"
