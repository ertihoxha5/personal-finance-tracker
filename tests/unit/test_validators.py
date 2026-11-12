import dataclasses
import logging
from dataclasses import dataclass
from typing import Any, cast

import pytest

from pft.domain.exceptions import (
    InvalidAccountNameError,
    InvalidAmountError,
    InvalidTextError,
)
from pft.domain.money import Money
from pft.domain.validators import (
    NonEmptyText,
    PositiveAmount,
    log_action,
    require_positive,
)

LOGGER = "pft.domain.validators"
ZERO = Money.zero()


class Payment:
    amount = PositiveAmount()
    label = NonEmptyText()

    def __init__(self, amount: Money, label: str = "synthetic") -> None:
        self.amount = amount
        self.label = label


@dataclass
class Entry:
    """Stands in for #14's Transaction: both descriptors on a dataclass."""

    amount: PositiveAmount = PositiveAmount()
    note: NonEmptyText = NonEmptyText()


@dataclass(frozen=True)
class FrozenEntry:
    amount: PositiveAmount = PositiveAmount()


# --- PositiveAmount -------------------------------------------------------------------


@pytest.mark.parametrize("value", ["0", "-5"])
def test_zero_or_negative_amount_raises_a_clear_error(value: str) -> None:
    with pytest.raises(InvalidAmountError, match="amount must be greater than zero") as info:
        Payment(Money.of(value))
    assert info.value.field == "amount"
    assert value.lstrip("-") in info.value.message


def test_positive_amount_is_accepted_and_read_back() -> None:
    payment = Payment(Money.of("12.50"))
    assert payment.amount == Money.of("12.50")


def test_reassignment_is_validated_too() -> None:
    payment = Payment(Money.of("1"))
    with pytest.raises(InvalidAmountError):
        payment.amount = Money.of("-1")
    assert payment.amount == Money.of("1")


def test_non_money_amount_is_rejected() -> None:
    with pytest.raises(InvalidAmountError, match="must be a Money value, got str"):
        Payment(cast(Any, "12.50"))


def test_each_instance_keeps_its_own_value() -> None:
    first, second = Payment(Money.of("1")), Payment(Money.of("2"))
    assert (first.amount, second.amount) == (Money.of("1"), Money.of("2"))
    assert vars(first)["_amount"] == Money.of("1")


def test_reading_before_assignment_raises_attribute_error() -> None:
    payment = Payment.__new__(Payment)
    with pytest.raises(AttributeError, match="amount has not been set"):
        _ = payment.amount


def test_class_access_raises_attribute_error() -> None:
    with pytest.raises(AttributeError):
        _ = Payment.amount
    assert isinstance(vars(Payment)["amount"], PositiveAmount)


# --- NonEmptyText ---------------------------------------------------------------------


@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
def test_empty_or_whitespace_text_is_rejected(text: str) -> None:
    with pytest.raises(InvalidTextError, match="label must not be empty") as info:
        Payment(Money.of("1"), text)
    assert info.value.field == "label"


def test_non_string_text_is_rejected() -> None:
    with pytest.raises(InvalidTextError, match="must be text, got int"):
        Payment(Money.of("1"), cast(Any, 42))


def test_text_is_stored_stripped() -> None:
    assert Payment(Money.of("1"), "  Groceries  ").label == "Groceries"


def test_custom_error_class() -> None:
    class Named:
        name = NonEmptyText(error=InvalidAccountNameError)

    with pytest.raises(InvalidAccountNameError, match="name must not be empty"):
        Named().name = " "


# --- Dataclass integration (de-risks #14) ---------------------------------------------


def test_dataclass_valid_construction() -> None:
    entry = Entry(Money.of("3.20"), " Coffee ")
    assert entry == Entry(Money.of("3.20"), "Coffee")
    assert (
        repr(entry) == "Entry(amount=Money(amount=Decimal('3.20'), currency='EUR'), note='Coffee')"
    )


def test_dataclass_fields_stay_required() -> None:
    assert all(f.default is dataclasses.MISSING for f in dataclasses.fields(Entry))
    with pytest.raises(TypeError):
        Entry()  # mypy sees a default here; at runtime there is none


def test_dataclass_rejects_invalid_values() -> None:
    with pytest.raises(InvalidAmountError):
        Entry(Money.of("0"), "Coffee")
    with pytest.raises(InvalidTextError):
        Entry(Money.of("1"), "")


def test_frozen_dataclass_validates_and_stays_frozen() -> None:
    with pytest.raises(InvalidAmountError):
        FrozenEntry(Money.of("-1"))
    entry = FrozenEntry(Money.of("1"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.amount = Money.of("2")  # type: ignore[misc]


# --- @log_action ----------------------------------------------------------------------


@log_action("add")
def add_entry(amount: Money, note: str = "") -> str:
    """Add a synthetic entry."""
    return f"added {amount}"


@log_action("delete")
def delete_entry(entry_id: int) -> None:
    """Fail like a missing entry."""
    raise KeyError(entry_id)


def test_decorated_function_keeps_name_and_docstring() -> None:
    assert add_entry.__name__ == "add_entry"
    assert add_entry.__doc__ == "Add a synthetic entry."
    assert getattr(add_entry, "__wrapped__", None) is not None


def test_success_writes_exactly_one_info_line(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER):
        result = add_entry(Money.of("9.99"), note="private note")
    assert result == "added 9.99 EUR"
    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [
        (logging.INFO, "add: add_entry")
    ]
    assert "9.99" not in caplog.text
    assert "private note" not in caplog.text


def test_failure_writes_one_warning_and_reraises(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER), pytest.raises(KeyError):
        delete_entry(7)
    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [
        (logging.WARNING, "delete failed: delete_entry (KeyError)")
    ]


# --- @require_positive ----------------------------------------------------------------


@require_positive
def deposit(account_id: int, amount: Money) -> Money:
    """Deposit a synthetic amount."""
    return amount


def test_require_positive_accepts_positional_and_keyword_amounts() -> None:
    assert deposit(1, Money.of("5")) == Money.of("5")
    assert deposit(1, amount=Money.of("5")) == Money.of("5")
    assert deposit.__name__ == "deposit"


@pytest.mark.parametrize("amount", [Money.of("0"), Money.of("-5"), cast(Any, 5)])
def test_require_positive_rejects_bad_amounts(amount: Money) -> None:
    with pytest.raises(InvalidAmountError):
        deposit(1, amount)
    with pytest.raises(InvalidAmountError):
        deposit(account_id=1, amount=amount)


def test_require_positive_checks_a_default_amount() -> None:
    @require_positive
    def charge(amount: Money = ZERO) -> None: ...

    with pytest.raises(InvalidAmountError):
        charge()


def test_require_positive_needs_an_amount_parameter() -> None:
    with pytest.raises(TypeError, match="needs an 'amount' parameter"):

        @require_positive
        def no_amount(total: Money) -> None: ...


def test_stacked_decorators_log_rejected_amounts(caplog: pytest.LogCaptureFixture) -> None:
    @log_action("withdraw")
    @require_positive
    def withdraw(amount: Money) -> Money:
        """Withdraw a synthetic amount."""
        return amount

    with caplog.at_level(logging.INFO, logger=LOGGER):
        assert withdraw(Money.of("2")) == Money.of("2")
        with pytest.raises(InvalidAmountError):
            withdraw(Money.of("-2"))
    assert [r.getMessage() for r in caplog.records] == [
        "withdraw: test_stacked_decorators_log_rejected_amounts.<locals>.withdraw",
        "withdraw failed: test_stacked_decorators_log_rejected_amounts.<locals>.withdraw "
        "(InvalidAmountError)",
    ]
    assert withdraw.__doc__ == "Withdraw a synthetic amount."
