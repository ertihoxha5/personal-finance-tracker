# Task #14 – Transaction hierarchy: defense notes

## Abstraction: why `Transaction(...)` raises TypeError
- `Transaction` inherits from `ABC` and declares two abstract members:
  `signed_amount()` and the `kind` property (`@property` stacked on `@abstractmethod`).
- `ABCMeta` records the abstract names in `__abstractmethods__`. Creating an instance of a
  class that still has any raises `TypeError: Can't instantiate abstract class`.
- That is the point: "a transaction" with no kind has no sign, so it must not exist. Only
  `Income`, `Expense` and `Transfer`, which implement both members, can be created.

## Inheritance
- The base class holds what every transaction shares: `id`, `account_id`, `amount`,
  `date`, `category`, `note`, plus validation (`__post_init__`), `to_row()`, `__lt__` and
  `copy_for()`. Subclasses inherit all of it and only add what is different.
- `Transfer` adds `direction` and `transfer_id`, redefines `category` with a default
  (`Category.OTHER`), extends `__post_init__` with `super().__post_init__()`, extends
  `to_row()` the same way, and overrides `copy_for()` to refuse.

## Polymorphism: one call, three behaviours
```python
total = sum((t.signed_amount() for t in transactions), Money.zero())
```
- The loop never asks which class `t` is. Income returns `+amount`, Expense returns
  `−amount`, Transfer returns `−amount` for OUT and `+amount` for IN.
- Adding a new kind later means adding a class, not editing every `if kind == ...`
  across the code (open/closed principle). `Account.balance` already works this way: it only
  needs `signed_amount()` (its `AccountTransaction` Protocol), and a test adds real Income
  and Expense objects to an Account.

## Dataclasses, and the two bugs in the plan's sketch
- `@dataclass` writes `__init__`, `__repr__` and `__eq__` from the annotated fields.
- **Field order bug:** the base class has fields with defaults (`note`). If `Transfer` adds
  `direction` without a default, Python refuses: "non-default argument follows default
  argument". `@dataclass(kw_only=True)` on every class makes all parameters keyword-only, so
  order no longer matters. It also makes calls readable and safe:
  `Expense(id=1, account_id=1, amount=..., date=..., category=...)`; positional calls fail.
- **Shadowing bug:** `date: date` makes the field name hide the type in the class body. We
  `import datetime as dt` and write `date: dt.date`.

## The amount field and the #12 descriptor
- `amount: PositiveAmount = PositiveAmount()` validates on construction *and* on every later
  assignment (`t.amount = Money.of("-1")` raises). The amount is stored positive; the kind
  gives the sign, as Appendix B requires.
- `PositiveAmount.__get__` raises on class access, so `dataclass` sees no default and
  `amount` is still required at runtime. mypy thinks it has a default; a test covers the
  difference (`Expense(...)` without amount is a TypeError).
- No `slots=True` and not frozen: the descriptor stores the value in the instance `__dict__`.

## Validation in `__post_init__`
- `date` must be a `date` but not a `datetime`. `datetime` is a subclass of `date`, so
  `isinstance` alone would let it through; then `date < datetime` raises TypeError in
  `sorted()`. Raises `InvalidDateError(field="date")`.
- `category` must be a `Category` member (`InvalidCategoryError`), `direction` a `Direction`
  member (`InvalidChoiceError`). The note is optional text and is stripped.
- `transfer_id` uses the #12 `NonEmptyText` descriptor.

## Sorting, equality and hashing
- `__lt__` compares dates only and returns `NotImplemented` for anything else (Python then
  raises TypeError). `sorted()` only needs `<`. It is stable, so same-day transactions keep
  their order. We don't use `order=True` (it compares all fields as a tuple, id first) or
  `total_ordering`.
- `__eq__` (from the dataclass) compares all fields including `id` and the class.
- A mutable dataclass with `__eq__` gets `__hash__ = None`: transactions can't go in a set
  or be dictionary keys. That is correct, because a hash must not change while the object
  is in a set, and these objects can change. Key by `t.id` instead.

## `to_row()` and `CSV_COLUMNS`
- One constant: `id, account_id, kind, amount, currency, date, category, note, transfer_id,
  direction`. `to_row()` returns exactly those keys in that order, every value a string:
  `"64.50"` (exact Decimal text), ISO date, enum values (`"food"`), and empty strings for the
  transfer columns on Income/Expense. #17 `from_row` and the #18 repository read the same constant.

## `copy_for(new_date, *, new_id)` for recurring items
- `dataclasses.replace(self, date=..., id=...)` builds a new object through `__init__`, so
  the copy is validated again; the original is untouched. `Self` keeps the subclass type
  (an Expense copy is an Expense).
- IDs are ints assigned by the Ledger/repository, so the caller passes the new ID.
- `Transfer.copy_for` raises `InvalidTransferError`: a copy would reuse `transfer_id` and link
  unrelated transfer pairs. Recurring transfers are not supported.

## Decisions (12 Nov 2026)
- IDs are `int` (`id`, `account_id`), matching Account, Ledger, filters and SQLite, instead
  of the sketch's `str` uuid.
- New enum `Direction` (`out`, `in`) next to `Kind`; new exception `InvalidTransferError`
  (`invalid_transfer`).
- Transfer category defaults to `OTHER`; reports exclude transfers by kind.

## React deliverable
- `TransactionForm` (shared income/expense form): kind radio, account, `MoneyInput`, date
  (defaults to today in the *local* time zone; `toISOString()` would give the UTC date),
  category with labels, optional note. It reuses the #12 `useFormValidation` hook: errors
  shown inline, focus on the first invalid field, server errors beside their fields
  (`account_id` from the API is mapped to the account select), input kept, no double submit.
- `toDto` builds the body: amount as a decimal string, ISO date, enum values, integer
  account id. Its keys are a subset of `CSV_COLUMNS` (a test reads the Python file).
- `TransactionRows`: every row names its kind in text with a sign: `+ Income`, `− Expense`,
  `− Transfer out`, `+ Transfer in`, and the amount is signed (`−€64.50`). Colour is only an
  extra cue, so colour-blind users and screen readers get the same information
  (WCAG 1.4.1, use of colour).
- `/dev/transactions` (DEV only): the form with fixture responses and rows of all three kinds.
