# Task #10 – Enums and exceptions: defense notes

## Why Enum instead of plain strings
- A plain string allows typos: `"fodo"` is a valid `str`, but `Category.FODO` is an
  `AttributeError` when the code runs, and mypy and the editor catch it before that.
- The list of allowed values lives in one place. `for c in Category` gives every value,
  which is how the error message lists all valid categories without repeating them.
- Members are singletons, so `is` works: `Category.from_text("food") is Category.FOOD`.

## Why StrEnum with lowercase values (team decision)
- `StrEnum` (Python 3.11+) members are real strings: `Category.FOOD == "food"`,
  `str(Category.FOOD) == "food"`, and `json.dumps` writes `"food"` with no custom encoder.
  JSON, CSV and SQLite all store the value without any conversion.
- With a plain `Enum`, `str(Category.FOOD)` would be `"Category.FOOD"`, and every
  serialiser would need `.value`.
- Lowercase values are the API contract. React's `labels.js` maps them to display text
  (`food → Food`), so the UI wording can change without changing stored data.

## Class methods: `from_text` as an alternative constructor
- `Category("food")` (the normal enum lookup) is exact and case-sensitive, and raises
  `ValueError`. That suits code, not user input.
- `Category.from_text(" FOOD ")` is a `@classmethod`. It receives the class (`cls`) rather
  than an instance, so it can build and return a member. It's the same idea as
  `Money.of("12.50")` from #06: a named second way to create the object.
- It strips whitespace, ignores case, and raises `InvalidCategoryError` (a
  `FinanceError`), never a bare `ValueError`. The message lists every valid value.
- Kind, AccountType and Frequency share the same `_parse` helper, so the four enums can't
  parse differently. #17 TransactionFactory uses `Kind.from_text`.

## Frequency.next_date and month ends
- `WEEKLY` adds 7 days. `MONTHLY` uses the plan's `add_month`: the next month, with the
  day clamped to `calendar.monthrange` (31 Jan → 28 Feb 2027, 29 Feb in 2028). `YEARLY`
  turns 29 Feb into 28 Feb in a non-leap year.
- `next_date` is a normal method on the enum: members can have behaviour, not just values.
- **Drift:** clamping loses the original day, so chaining calls gives
  31 Jan → 28 Feb → 28 Mar. Recurring transactions (#25) must compute each occurrence
  from the original start date, not from the previous occurrence. A test pins this down.

## Custom exception hierarchy: catch FinanceError once
- Every domain error inherits from `FinanceError`. The CLI and API catch that one type and
  show `str(error)`, so no invalid input ever produces a traceback (FR-23). Programming
  bugs (`TypeError`, `KeyError`) are not `FinanceError`s, so they stay loud.
- Subclasses let callers be specific when it matters: `except AccountNotFoundError` → 404,
  `except InvalidCategoryError` → re-ask the user.
- `InvalidCategoryError` is a subclass of `InvalidChoiceError`, which the other enums
  raise. Code can catch "any bad choice" or "a bad category" specifically.
- Every class has a stable `code` (e.g. `"invalid_amount"`), and an error can name the
  `field` it belongs to. `to_dict()` returns `{code, message, field}`, the API error shape
  the team agreed. React decides based on `code` and `field`, never on parsing message text.
- `exceptions.py` imports nothing from `pft`, so any module can import it without
  creating an import cycle. A test checks this.

## React side
- `lib/labels.js`: `CATEGORY_LABELS`, `ACCOUNT_TYPE_LABELS`, `KIND_LABELS` and
  `FREQUENCY_LABELS`, keyed by the API values. Unknown values fall back to a readable
  form (`credit_line → Credit line`) instead of showing nothing. A test reads
  `category.py` and fails if a key drifts from the Python values.
- `lib/apiErrors.js`: `mapApiError(error)` returns `{ fieldErrors, pageAlert }`:
  - errors with a `field` go under that input;
  - everything else goes to one page alert;
  - network failures (`TypeError` from `fetch`) and 5xx errors can be retried;
  - 4xx domain errors can't, because they'd fail the same way again.
- Inline messages: `MoneyInput` and `SelectField` take an `error` prop and link it with
  `aria-describedby`, plus `aria-invalid` on the input.
- `PageAlert`: `role="alert"` so screen readers announce it. It gets focus when it
  appears, has **Try again** only when retrying can help, and always has **Dismiss**.
- Demo: `/dev/errors` (dev builds only) shows each failure scenario, the
  `mapApiError` output and the label table.

## Tests
- `tests/unit/test_category.py`, `tests/unit/test_exceptions.py`
  (all four done-when checks plus edge cases: spaces/caps, Dec → Jan, leap year,
  29 Feb yearly, weekly across a month end, str round-trip, drift).
- `frontend/tests/labels.test.mjs`, `frontend/tests/apiErrors.test.mjs`
  (`node --test frontend/tests/*.test.mjs`).
