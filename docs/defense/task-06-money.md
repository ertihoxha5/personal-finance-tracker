# Task #06 – Money: defense notes

## Value object
`Money` is defined only by its value (amount + currency), not by an identity. Two
`Money("5.00", "EUR")` objects are equal and interchangeable, have the same hash, and
can be used as dict keys or in sets. It is immutable: every operation returns a new
`Money`, so a value passed around the app can never be changed behind your back.

## Dataclasses
`@dataclass(frozen=True, slots=True)` writes `__init__`, `__repr__`, `__eq__` and
`__hash__` for us.
- `frozen=True`: assigning to a field raises `FrozenInstanceError`. That's why
  `__post_init__` uses `object.__setattr__` to store the normalised amount once.
- `slots=True`: no per-instance `__dict__`, so it uses less memory and you can't add stray
  attributes.
- `__post_init__` runs after the generated `__init__` and is where validation and
  rounding happen. An invalid `Money` can never exist.
- `@functools.total_ordering` fills in `<=`, `>`, `>=` from `__lt__` and `__eq__`.

## Operator overloading
`+`, `-`, unary `-`, `*` and `<` are implemented by `__add__`, `__sub__`, `__neg__`,
`__mul__`/`__rmul__` and `__lt__`.
- Returning `NotImplemented` (not raising) tells Python to try the other operand's
  method. If that also fails, Python raises `TypeError`. This is why `Money * Money` and
  `Money * 1.5` give a `TypeError`.
- `__radd__` accepts only the integer `0`, because `sum()` starts from `0`:
  `0 + Money` → `Money.__radd__(0)`. Prefer `sum(items, Money.zero())`, which also
  returns `Money` for an empty list.
- Different currencies: `+`, `-` and `<` raise `CurrencyMismatchError`, but `==` just
  returns `False`. Equality must never raise, otherwise `in` checks and sets would
  break.

## Why Decimal, not float
- Floats are binary fractions, and 0.1 has no exact binary form:
  `0.1 + 0.2 == 0.30000000000000004`. `Decimal("0.10") + Decimal("0.20")` is exactly
  `0.30`.
- Rounding: the float `2.675` is really 2.67499999…, so `round(2.675, 2)` gives
  `2.67`. `Decimal("2.675")` rounded to cents with `ROUND_HALF_UP` gives `2.68`, which
  is the rule people expect.
- That's why `Money(0.1)` is rejected: the error is already inside the float before
  `Money` sees it. Build from strings: `Money.of("0.10")`.
- `bool` is rejected because `True` is an `int` in Python and would silently become
  1.00.
- NaN and Infinity are rejected because they aren't amounts of money.

## Edge cases we handle
- Negative zero: `Money.zero() * -1` would print `-0.00`, so it's normalised to `0.00`.
- Very large values: quantizing beyond Decimal's 28-digit precision raises
  `InvalidOperation`, which we wrap as `InvalidAmountError`.
- Currency must be three upper-case letters, so a typo like `"eur"` can't become a
  separate currency.

## React side
- The API sends amounts as decimal strings. `formatEUR` (lib/money.js) is the only
  place `Number()` touches money, and only to display it with `Intl.NumberFormat`
  (`en-IE`, real minus sign `−`, zero always `€0.00`).
- `MoneyInput` is a text input with `inputMode="decimal"`, not `type="number"`.
  `type="number"` rejects `12,50` in some browsers, changes the value on scroll, and
  returns a float. Parsing is done on the string, so `12,5` becomes `"12.50"` without
  any floating-point maths.
