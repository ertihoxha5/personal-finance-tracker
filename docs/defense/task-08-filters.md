# Task #08: composable filters

## Python interface

`pft/services/filters.py` uses the planned Transaction attributes: `category`,
`kind`, `account_id`, `date` and unsigned `amount: Money`. A read-only Protocol
allows the future Transaction class to work without inheritance or changes to
the existing Money, Account or enum implementations.

- `by_category(*cats)` matches any selected category. No categories matches none.
- `by_kind(kind)` and `by_account(account_id)` use equality.
- `between(start, end)` and `amount_between(lo, hi)` include both bounds.
  Reversed bounds raise ValueError; Money enforces currency compatibility.
- `all_of(*preds)` combines with AND; no predicates accepts everything.
- `any_of(*preds)` combines with OR; no predicates accepts nothing.
- `apply_filters(items, *preds)` returns a single-pass generator. It evaluates
  predicates only as items are requested and preserves order, object identity
  and concrete transaction type. It does not copy the source into a list.

```python
from pft.domain.money import Money
from pft.services.filters import (
    any_of,
    apply_filters,
    by_account,
    by_category,
    month_preset,
)

# `food` is the agreed category value; `items` is an iterable of transactions.
selected = apply_filters(
    items,
    by_category(food),
    lambda transaction: transaction.amount > Money.of("20.00"),
)

november = month_preset(2026, 11)  # functools.partial binding between's bounds
selected = apply_filters(items, november(), any_of(by_account(1), by_account(2)))
```

The example's `items` and `food` are supplied by the caller after domain
integration. `month_preset` handles leap years and December explicitly through
calendar boundaries; it does not freeze today's date at module import.

## React preview

Run the frontend and visit `/transactions`. The screen combines category
checkboxes (OR within the selection) with type, account, inclusive date and
amount bounds, and case-insensitive note search (AND across filter groups).
Empty UI selections omit that filter. Reset clears every field, validation
error and active-filter label. Invalid ranges suppress results and show linked
field messages. No matches shows an explanatory empty state.

Amounts remain decimal strings. The fixture helper compares integer cents using
BigInt; it does not calculate balances or report totals. Expenses use unsigned
amount magnitudes for filtering and negative signs for display. Transfer rows
show their in/out direction in text.

This is a synchronous, synthetic preview with its own fixtures, independent of
the Accounts screen. It does not read or write SQLite or expose a new FastAPI
endpoint. Loading and network-failure states do not apply to this local source.
When the transaction API exists, route live filtering through the Python
predicates, map the agreed enum values, and add the applicable network states.
Note search is included for #08's React deliverable; broader search/sorting
remains part of #15.

## Checks and review evidence

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
node --test frontend/tests/transactionFilters.test.mjs
```

From `frontend`, run `npm run lint` and `npm run build`.

Final automated review: 96 Python test cases passed, including 32 filter cases;
the filter module has 100% statement coverage (97% overall). All six frontend
filter regression tests passed. Ruff lint, formatting and mypy passed.

Browser observations during Part 4:

- Desktop: all 10 initial rows; Food plus minimum 20.01 returned 3 rows.
- Adding unmatched note text produced 0 rows and the empty-results message.
- Reset cleared text fields and restored all rows.
- Tab from Reset and Space selected Food with a visible focus indicator.
- At 390px viewport width, the header, category checkboxes and upper select
  fields fit and stack without clipping.

The lower mobile fields and horizontal results-table interaction still need
human verification; the automated browser bridge was unavailable and native
interaction stopped when user input was detected and Chrome was minimized.
Before reviewer approval,
check the following in Chrome at 390px:

1. Enter minimum 30 and maximum 20; verify the linked range error and hidden rows.
2. Reset; verify 10 rows and no active filters or errors.
3. Scroll the results table horizontally with keyboard focus on its region.
4. Combine account, type, both date bounds and a note; verify the result and labels.

For the defense, explain higher-order functions (builders return predicates),
closures (predicates retain bounds), short-circuit composition, lazy generators
and partial application. Tests use stubs until the Transaction task is merged.
AI assistance was used to implement the filters, fixtures, UI and test cases;
the project plan and existing source interfaces informed the implementation.
