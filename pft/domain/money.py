"""Money value object.

Amounts are exact Decimals rounded to cents (ROUND_HALF_UP), never floats:
0.1 + 0.2 is 0.30000000000000004 as a float but exactly 0.30 here. Money is
immutable and compares by value, so two Money objects with the same amount and
currency are interchangeable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import total_ordering

from pft.domain.exceptions import (
    CurrencyMismatchError,
    InvalidAmountError,
    InvalidCurrencyError,
)

CENT = Decimal("0.01")
DEFAULT_CURRENCY = "EUR"
_CURRENCY_CODE = re.compile(r"[A-Z]{3}")


def _to_amount(value: object) -> Decimal:
    """Convert an int, str or Decimal into a finite Decimal rounded to cents."""
    # bool is a subclass of int, so it must be rejected before the int branch.
    if isinstance(value, bool | float):
        raise InvalidAmountError(
            f"{type(value).__name__} is not allowed for money; pass a str, int or Decimal"
        )
    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, int | str):
        text = str(value).strip()
        if "_" in text:
            raise InvalidAmountError(f"invalid amount: {value!r}")
        try:
            amount = Decimal(text)
        except InvalidOperation as exc:
            raise InvalidAmountError(f"invalid amount: {value!r}") from exc
    else:
        raise InvalidAmountError(f"unsupported amount type: {type(value).__name__}")

    if not amount.is_finite():
        raise InvalidAmountError(f"amount must be finite, got {value!r}")
    try:
        rounded = amount.quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise InvalidAmountError(f"amount is too large: {value!r}") from exc
    # Turn -0.00 into 0.00 so it never prints as "-0.00".
    return abs(rounded) if rounded.is_zero() else rounded


@total_ordering
@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str = DEFAULT_CURRENCY

    def __post_init__(self) -> None:
        if not isinstance(self.currency, str) or not _CURRENCY_CODE.fullmatch(self.currency):
            raise InvalidCurrencyError(f"currency must be a code like 'EUR', got {self.currency!r}")
        # The dataclass is frozen, so the normalised value is stored with object.__setattr__.
        object.__setattr__(self, "amount", _to_amount(self.amount))

    @classmethod
    def of(cls, value: Decimal | int | str, currency: str = DEFAULT_CURRENCY) -> Money:
        """Typed factory for building Money from a str or int."""
        return cls(_to_amount(value), currency)

    @classmethod
    def zero(cls, currency: str = DEFAULT_CURRENCY) -> Money:
        return cls(Decimal(0), currency)

    def _check(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"cannot combine {self.currency} with {other.currency}")

    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._check(other)
        return Money(self.amount + other.amount, self.currency)

    def __radd__(self, other: int) -> Money:
        # sum() starts from the integer 0; accept exactly that and nothing else.
        if type(other) is int and other == 0:
            return self
        return NotImplemented

    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._check(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def __mul__(self, factor: int | Decimal) -> Money:
        # Only int or Decimal factors; Money * Money and Money * float make no sense.
        if isinstance(factor, bool) or not isinstance(factor, int | Decimal):
            return NotImplemented
        return Money(self.amount * factor, self.currency)

    __rmul__ = __mul__

    def __lt__(self, other: Money) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._check(other)
        return self.amount < other.amount

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"
