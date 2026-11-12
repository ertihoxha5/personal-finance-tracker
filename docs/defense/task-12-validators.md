# Task #12 – Validators: descriptors and decorators: defense notes

## The goal: write each rule once
- "An amount must be positive Money" lives in one private function, `_ensure_positive`.
  The `PositiveAmount` descriptor and the `@require_positive` decorator both call it, so
  the rule and its message can't drift apart.
- The errors are `FinanceError`s with a `field` (`InvalidAmountError(..., field="amount")`),
  so the API can send `{code, message, field}` and React shows the message beside the input.

## The descriptor protocol
- A descriptor is an object stored as a class attribute that defines `__get__`, `__set__`
  and/or `__delete__`. Python calls them when the attribute is read or assigned on an
  instance. One with `__set__` is a *data descriptor* and wins over the instance `__dict__`.
- `__set_name__(owner, name)` runs once when the class is created. It tells the descriptor
  its own name (`"amount"`), so it can store the value as `_amount` and name the field in
  error messages. Without it you would write `PositiveAmount("amount")` by hand.
- `__set__` validates and stores the value **on the instance** (`vars(obj)["_amount"]`).
  The descriptor object is shared by every instance, so storing on `self` would give all
  objects the same amount.
- `__get__(None, cls)` is class access (`Payment.amount`). The plan sketch returns `self`
  there; we raise `AttributeError` instead. Reason: `@dataclass` reads the class attribute
  to find a field's default. Returning the descriptor would make the descriptor object the
  default amount, so `Transaction()` would silently "work". Raising makes `dataclass` see no
  default, and the field stays required (tested in `test_dataclass_fields_stay_required`).

## Why a descriptor and not `@property`
- A property has to be written out for each attribute in each class: a getter, a setter,
  and a private name. Five validated fields means five copies of the same code.
- A descriptor is a reusable property: `amount = PositiveAmount()` in any class, and every
  assignment, including the one in `__init__`, is checked. An object can't be built or
  changed into an invalid state.

## Dataclass rules (for #14 and Account)
- Write `amount: PositiveAmount = PositiveAmount()`. Annotated with the descriptor type,
  mypy types the `__init__` parameter and `obj.amount` as `Money`. The one gap: mypy thinks
  the field has a default; at runtime it doesn't.
- No `slots=True`: the value is stored in the instance `__dict__`, and slotted classes have none.
- `frozen=True` works: the frozen `__init__` uses `object.__setattr__`, which still calls the
  descriptor; the descriptor writes into `__dict__` directly. Later assignments are blocked
  by the frozen `__setattr__` (tested).

## `NonEmptyText` and the error it raises (team decision, 12 Nov)
- It rejects non-strings and empty/whitespace text and stores the stripped value.
- It takes the error class as a parameter: `NonEmptyText(error=InvalidAccountNameError)`.
  The default is the new `InvalidTextError` (`code = "invalid_text"`). This adds one class to
  the #10 hierarchy and moves nothing, so every existing `code` stays the same.
- It is meant for account names, not transaction notes: the #14 sketch defaults the note to
  an empty string. `Account` already rejects empty names; switching it to the descriptor is
  Florent's call.

## Decorators with arguments: three nested functions
```python
@log_action("add")        # 1. log_action("add") runs first and returns `decorator`
def add(...): ...         # 2. decorator(add) returns `wrapper`
                          # 3. calling add(...) now runs wrapper(...)
```
- The outer function holds the argument (`action`) in a closure, `decorator` receives the
  function, and `wrapper` runs on every call.
- `@require_positive` has no arguments, so it's only two levels: `decorator(func) -> wrapper`.

## What `functools.wraps` preserves
- It copies `__name__`, `__qualname__`, `__doc__`, `__module__`, `__annotations__` and
  `__dict__` from the original onto the wrapper and sets `wrapper.__wrapped__ = func`.
- Without it every decorated function would be called `wrapper` with no docstring: logs,
  tracebacks, `help()` and pytest output would all show the wrong name.
- `inspect.signature` follows `__wrapped__`, which is why `@require_positive` still finds the
  `amount` parameter when it sits under `@log_action` (tested with both stacked).

## `@require_positive` finds `amount` through the signature
- `inspect.signature(func).bind(*args, **kwargs)` maps the call to parameter names, so
  `deposit(1, m)` and `deposit(1, amount=m)` are both checked. `apply_defaults()` also checks
  a default amount.
- A function without an `amount` parameter is a `TypeError` when it is decorated (at import),
  not a surprise at the first call.

## Logging: logger vs print, exactly one line
- `log = logging.getLogger(__name__)` gives a named logger (`pft.domain.validators`). Levels,
  handlers and the log file are configured once at the entry point (CLI/API), so the module
  has no side effects on import and tests can capture output with `caplog`.
- `print` can't be filtered by level, turned off, sent to a file or captured per test.
- Every decorated call writes exactly one line: INFO `add: add_entry` on success, or
  WARNING `add failed: add_entry (KeyError)` and then the exception is re-raised. The
  failure line goes beyond the sketch so a failed action isn't invisible in the log.
- Only the action, function and error type are logged, never arguments: amounts and notes
  are personal data and stay out of log files (tested).
- `log.info("%s: %s", action, name)` passes arguments instead of an f-string, so the message
  is only formatted if the level is enabled.

## Typing (mypy strict, Python 3.11 floor)
- `ParamSpec("P")` and `TypeVar("R")` let the wrapper keep the decorated function's exact
  signature: `Callable[P, R] -> Callable[P, R]`. mypy still checks calls to decorated functions.
- The `def f[T]()` syntax would be shorter but needs Python 3.12.
- The base class `_Validated(Generic[T])` types `__get__` as returning `T` and `__set__` as
  taking `T`, so `PositiveAmount` is `Money` in and out and `NonEmptyText` is `str`.

## React deliverable
- `lib/validation.js`: `required(value)` and `positiveDecimal(text)`. `positiveDecimal` reuses
  `parseMoneyInput` from #06 and rejects zero by comparing the normalised string to `0.00`:
  no `parseFloat`, no `Number()` (a test checks the source).
- `hooks/useFormValidation.js`: nothing is checked until the first submit; after that every
  change re-validates. Focus goes to the first invalid field. Server errors go through
  `mapApiError` (#10): errors for fields in the form appear beside them, everything else in
  the `PageAlert`. A server error for a field the form doesn't have also goes to the alert,
  so it can't be lost. Values are never reset on error.
- Double submission: `submitting` disables the button with `aria-busy`, and a `useRef` guard
  at the top of `handleSubmit` drops repeats. The guard is what matters: pressing Enter in a
  text field submits the form even when the button is disabled, and a ref updates
  immediately, while state only changes on the next render.
- `/dev/validation` (DEV only) has fixture responses for success, a field error, a page error
  and a slow response. The real transaction form is #14.
