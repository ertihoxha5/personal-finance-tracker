# Task #21 – First CLI commands: defense notes

## Layers
- `pft/cli.py` is the outermost layer. It parses what the user typed, asks the Repository for the
  Ledger, calls the domain and services, saves after every change, and prints. The domain, services
  and repositories never print; only the CLI (and the API for JSON) talks to the outside.
- The React app uses the same Python code through FastAPI, so a transaction added in the CLI shows
  up in the browser and the other way round (checked by hand on one SQLite file).

## argparse
- Sub-commands: `init`, `serve`, `account add|list`, `add income|expense AMOUNT CATEGORY`, `list`,
  `balance`, `report monthly`. Nested sub-parsers (`account add`, `report monthly`) keep each
  command's options separate. `--help` works on every one of them (a test walks them all).
- Usage mistakes (missing command, unknown option) are reported by argparse with exit code 2.
- `--account` accepts a name in any case or an ID. With exactly one account it may be left out.

## match / case
- `_run` dispatches on `args.command` with structural pattern matching (nested for `account` and
  `report`), instead of an if/elif chain. An unknown command cannot reach it because argparse
  already refuses it.

## Errors and exit codes
- `main()` catches every `FinanceError`, prints `Error: <message>` to stderr and returns 1.
  Bad amount, bad date, unknown category, unknown account, a transfer typed as `add`, bad month,
  bad sort key: none shows a traceback (parametrized test checks stdout is empty and there is no
  "Traceback"). A failed command changes nothing, because the save happens only after success.
- Unexpected errors (real bugs) are not hidden; they would still show a traceback.

## Persistence
- Each command loads the Ledger from SQLite and, when it changed something, saves it through
  `SqliteRepository` (one transaction). Tests start a "new program" for every call, which proves
  "the data is still there after a restart". `PFT_DB_PATH` selects the database file.

## Filters, sorting and reports reuse existing services
- `list` builds predicates with `by_account`, `by_kind`, `by_category`, `month_preset`,
  `text_contains`, combines them with `apply_filters` and sorts with `sort_transactions` (#8, #15).
- `report monthly` prints `MonthlySummary` (#19). `parse_month` now lives in `services/reports.py`
  and is shared by the CLI and the API.

## React deliverable
- Shared fetch client: `src/api/http.js` (from #18) is used by the account, transaction and
  dashboard clients. Failures arrive as `ApiError` with message, field, status and code.
- Account, transaction and monthly-summary routes are connected. New in this task:
  `GET /api/transactions` (filters `account_id`, `kind`, `category`, `start`, `end`,
  `min_amount`, `max_amount`, `q`, `sort`, `direction`, applied by the Python predicates) and the
  Transactions page, which now lists from the API, filters on the server and adds transactions
  through the shared form with "Saving… / All changes saved / Not saved".
- Loading, empty, error and "Try again" states exist for the list. Server field errors appear
  under the matching form field.
- The CLI is kept as it is. Nothing in the React work replaces or removes a CLI command.
- Checked in the browser: list, add with a decimal comma, server-side note search, stopping the
  backend (error and retry shown); the CLI listed the transaction added in the browser.

## Known limits
- CLI amounts are shown with the currency "EUR" only; the app is EUR-only for now.
- `add transfer` is refused with a clear message until `Ledger.transfer` exists (#26).
- The Transactions page's older client-side filter helpers (`lib/transactionFilters.js`) are kept for
  validation and their tests; the page itself no longer filters in the browser.
- There is no CLI command to edit or delete a transaction or account yet.
