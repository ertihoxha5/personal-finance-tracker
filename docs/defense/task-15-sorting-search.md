# Task #15: sorting and text search

## Python implementation

`pft/services/filters.py` adds `text_contains(text)` and
`sort_transactions(items, key="date", reverse=False)` to #08's filters.

- `text_contains` searches the note using casefold, ignoring surrounding search
  whitespace. An empty search matches every transaction, including empty notes.
- Sorting accepts `date`, `amount` and `category`. `operator.attrgetter` supplies
  the key function. An invalid key raises ValueError listing those three choices.
- Python's stable sort preserves input order for equal keys in either direction.
  Sorting consumes the iterable and returns a new list containing the original
  transaction objects. It accepts the generator returned by `apply_filters`.
- Amount sorting uses positive Money magnitudes. Money rejects comparisons
  between currencies. Category sorting uses the Category StrEnum value.

```python
from pft.services.filters import apply_filters, sort_transactions, text_contains

# items is an iterable of Transaction objects supplied by the caller.
matches = apply_filters(items, text_contains("lunch"))
largest_first = sort_transactions(matches, "amount", reverse=True)
```

The read-only transaction Protocol now includes `note`, matching #14's real
Transaction interface. The #08 test stub supplies an empty note by default.
The #15 tests use real Income and Expense objects.

## Transactions screen

At `/transactions`, Sort by offers Date, Amount and Category, with Ascending
and Descending directions. The default is date ascending. Filter fields,
note search and sorting share the same React state. Reset filters and sorting
restores that default and clears all filter fields. The result count announces
the current sorting, including when a search has no matches.

`selectTransactions` applies filters and then sorts the result used by the
table. The frontend amount comparator uses BigInt cents to preserve decimal
precision. Equal keys retain source order. Existing synthetic data remains
the source for this screen. Future API integration should apply the Python
sorting and search functions to live transactions.

Python search uses Unicode casefold. The existing frontend preview search
uses locale lowercasing, so advanced Unicode cases such as Straße/STRASSE
currently differ between preview and backend. Both support case-insensitive
search for the English synthetic notes used by this task.

## Automated verification

Final checks passed on Python 3.12 and Node 24:

- 264 Python test cases, including 20 new sorting/search cases.
- 100% statement coverage for `filters.py`, 99% overall Python coverage.
- 44 frontend test cases, including nine new sorting cases.
- Ruff lint, Ruff formatting, mypy, frontend lint and production build.

The sorting tests check ascending and descending order, stable ties, invalid
keys, exact amount comparisons, combined filtering/search/sorting, source
preservation, reset defaults and compatibility with older filter objects.

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
```

From `frontend`:

```powershell
node --test tests/*.test.mjs
npm run lint
npm run build
```

## Browser acceptance checklist

Browser verification is pending. The previous attempt was stopped because
Computer Use could not establish Chrome's current URL confidently. On retry,
the browser access host was unavailable and the selected Chrome review window
was minimized. The checks below list expected behavior and must be observed
before recording browser acceptance.

1. Open `/transactions`. Date ascending starts with Groceries before November
   and ends with December groceries.
2. Select Date descending. December groceries appears first and Groceries before
   November last. The two 5 November transfer rows retain their original order.
3. Select Amount descending. Monthly salary appears first at 2200.00, followed
   by November rent at 600.00. Amount ascending starts with Lunch with classmates.
4. Select Category in each direction. Food rows retain their original order
   within the group. Ascending starts with Food and descending with Transport.
5. Select Food, enter GROCERIES in Note contains and select Amount descending.
   The notes appear as Weekly groceries, December groceries, Groceries before November.
6. Enter an unmatched note. Verify the empty-results message, then reset and
   verify all ten rows, empty filter fields and Date ascending.
7. Use Tab and arrow keys to operate sorting with visible focus. At 390px width,
   verify both sort controls fit and the results table can scroll horizontally.

For the defense, explain key functions, `operator.attrgetter`, stable sorting,
generator consumption, amount magnitudes and composing search with filters.
AI assistance was used for implementation and testing, using task #15 of the
project plan and the existing source interfaces.
