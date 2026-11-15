# Task #28: optional features

## Scope decision

Erti selected all three optional features in the project conversation on
15 November 2026: undo/redo, bank CSV import and matplotlib PNG charts.
Implement them as separate modules with their own tests, followed by optional
React controls outside the core workflow. The selection is recorded here as
Erti's instruction; it does not claim that a team milestone meeting occurred.

## Part 1: Command pattern

`pft/services/commands.py` adds AddCommand, DeleteCommand and TransferCommand,
each implementing execute() and undo(). History has separate undo and redo
stacks. A new successful command discards redo; failures do not move the stacks.
The module uses the existing Ledger API without changing domain/service logic.

Commands own copies of transaction data so callers cannot mutate their snapshots.
Undo and redo preserve transaction IDs and shared transfer IDs. Deleting either
transfer leg captures both rows; undo validates both target accounts and IDs
before restoring. Undo refuses to remove records that changed outside history.
Redo of a transfer checks the current source balance again.

History is session-local and connected to the optional API/React workflow below.
It is not persisted across restarts. The integration commits history only when
repository saving succeeds and invalidates it after mutations outside the optional
workflow. Budget warning behavior remains the responsibility of BudgetMonitor;
this part does not change the previously reviewed warning behavior.

Tests cover balances, identity, linked-pair deletion/restoration, stack ordering,
redo clearing, empty history, failed operations, external edits, missing accounts,
mutable input isolation and monotonic allocation of new IDs after undo.

## Part 2: bank CSV import

`pft/infrastructure/importer.py` adds BankCsvImporter. The supported template is
`date,amount,category` with optional `note,currency` columns. Columns can be in
any order and header names ignore surrounding whitespace and case. Files use
UTF-8 with or without a BOM. The importer does not guess bank-specific layouts.

Positive signed amounts become income and negative amounts become expenses.
TransactionFactory provides existing date/category/amount validation. Quoted
decimal commas are accepted. Zero, malformed signs, ambiguous amounts, invalid
categories/dates and currency mismatches produce row errors. Transfers remain
linked operations and cannot be created as individual bank rows.

ImportResult contains accepted rows and ImportIssue objects with a row number,
reason and optional field. Row numbers are physical ending line numbers for CSV
records, including multiline notes. Wrong column counts reject that row; broken
CSV syntax, invalid headers and more than 10,000 data rows abort before mutation.
Blank rows are ignored. Headers without data are a valid empty import.

Preview uses an observer-free copy of the accounts and ID counters. It cannot
change live transactions or send live budget warnings. Import uses the normal
Ledger addition path and leaves repository saving to the caller. There is no
duplicate detection: importing a file twice imports its rows twice because the
template contains no unique bank transaction reference. The later preview UI
must make that explicit and must revalidate on confirmation.

Example synthetic CSV:

```csv
date,amount,category,note
2026-11-15,-12.50,food,Lunch with team
2026-11-16,100.00,salary,Example payment
```

Importer tests cover mixed valid/invalid input, precise amounts, CSV escaping,
BOM/Unicode, previews, currencies, schema errors, malformed quoting and limits.
API/React preview and confirmation are described in parts 4 and 5 below.

## Part 3: PNG charts

`pft/infrastructure/charts.py` adds `save_category_pie(report, path)` and
`save_monthly_trend(report, path)`. They consume CategoryReportData and
TrendReportData; they do not recalculate financial totals or change the Ledger.
Only plotting coordinates use floats. Labels use the exact report values.

Install with `.venv\Scripts\python.exe -m pip install -e ".[charts]"`.
Matplotlib is a separate optional extra and is loaded only on a render request.
The CI backend installs both dev and charts extras so chart tests actually run.
Without matplotlib, core imports still work and a chart request raises the
friendly ChartUnavailableError. Rendering tests skip without the extra; the
missing-dependency behavior test still runs.

The headless Agg canvas creates PNGs without opening windows or changing the
global pyplot backend. A rendering lock protects matplotlib's shared caches.
Images are 1200 x 720 with a category amount/percentage legend or distinct line
styles for income, expenses and net. Months with no data remain zero. An empty
category report produces an explanatory image rather than failing.

PNG output is written to a sibling temporary file and atomically replaced after
successful rendering; failures clean the temporary file and preserve an existing
destination. Tests verify PNG signatures, dimensions/decoding, plotted report
values, legend text, empty data, dependency errors and failed writes. Synthetic
pie and trend outputs were visually inspected for legibility and clipping.

## Part 4: optional API integration

The separate `pft/api/optional.py` router is mounted under `/api/optional`.
Core account, transaction, budget and repository operations remain unchanged.
All optional endpoints are disabled by default. Enable approved tools before
starting the backend in PowerShell:

```powershell
$env:PFT_OPTIONAL_FEATURES = 'undo,import,charts'
.venv\Scripts\python.exe -m pft serve
```

`GET /features` reports which tools are enabled. Features can be enabled
individually by using a comma-separated subset; disabled endpoints return 404.

### History

`POST /history` starts a token-scoped tools session; `GET /history/{token}`
returns can_undo/can_redo and clears history if outside changes are detected.
`POST /history/{token}` accepts add, delete, transfer, undo or redo actions.
Only actions made through this session are undoable. Tokens expire after an
hour of inactivity and the process keeps at most 64 sessions per store.

History.fork binds copied commands to the freshly loaded ledger. The API stages
changes through LedgerStore.write, then publishes the new history only after
save succeeds. Failed saves therefore preserve both persisted data and the
previous stacks. A fingerprint of accounts, transactions, recurring rules,
budgets and ID counters rejects operations based on outside changes. Changes
from another tools session also invalidate a stale session. This follows the
existing single-process API assumption; it is not a multi-worker history store.

### Imports and charts

`POST /import/preview` accepts account_id and csv_text and returns accepted rows,
errors and a revision. `POST /import/confirm` requires expected_revision and
revalidates the raw CSV inside the locked store write. Outside changes require a
new preview. A successful import changes the revision, preventing accidental
replay with the same preview. Repository failure leaves the preview retryable.
The JSON CSV text is capped at one million characters, in addition to the
importer's row limit. BudgetMonitor supplies warnings for accepted expenses.

`GET /charts/categories?start=YYYY-MM-DD&end=YYYY-MM-DD` and
`GET /charts/trend?end=YYYY-MM&months=6` return PNG attachments. Reports are
collected from the store before rendering; temporary files are discarded.
Missing matplotlib produces 503 with an installation message.

API tests use temporary SQLite databases and synthetic data. They cover feature
gates, persistence, save failures, stale sessions, paired transfers, import
confirmation/replay prevention, chart downloads and invalid inputs.

## Part 5: optional React workspace

`/tools` contains separate panels for HistoryTools, ImportTools and ChartTools.
The sidebar shows its link only when `/api/optional/features` enables a selected
feature. Panels also check their individual capability, and the backend gates
every operation. Visiting the URL while disabled shows a friendly disabled state.
Account lists and existing validation forms are reused; core screens retain their
existing operations and do not acquire undo/redo behavior implicitly.

History starts only on an explicit button click. Add, transfer, confirmed delete,
undo and redo call the token-scoped API. The panel refreshes its transaction list
and account data after a saved operation. Failed actions remain visible and offer
refresh/new-session recovery. Linked transfer deletion is explained in confirmation.

CSV input accepts a UTF-8 file or pasted text. Account/text changes invalidate
preview immediately, and pending operations disable controls. Accepted and rejected
rows are shown in accessible tables (first 100 of each, with full counts). Only a
matching preview with accepted rows enables confirmation. After a successful import,
confirmation is disabled until another preview. The duplicate-file limitation is
visible. Backend warnings are displayed after imports/history operations.

PNG forms use inclusive dates for category charts and an ending month/count for
trends. Download names identify the selected range. The client checks image/png,
reports dependency/server errors, and prevents duplicate pending downloads.

Added frontend API contract tests and component interaction checks with jsdom and
React Testing Library. Components are compiled with the project's esbuild; tests
interact with the actual controls using mocked HTTP responses. They verify feature
gating, matching previews, changed text, row errors, confirmation outcomes, history
reset state and PNG filter/filename selection. CI now runs frontend tests as well
as lint/build. These checks do not claim a live Chrome/Firefox browser walkthrough.

## Live UI acceptance checklist

Start the backend in your own terminal with the environment variable in part 4,
then start the frontend with `npm run dev` in `frontend`. Open `/tools` via the
Optional tools sidebar link.

1. Start a history session. Add a synthetic expense, undo it and redo it. Verify
   both the transaction list and the Accounts balance after visiting Accounts.
2. From tools transfer between two synthetic accounts, undo/redo, then delete one
   transfer leg with confirmation. Undo and verify both linked rows return.
3. Change a record on a core screen, return to tools and refresh history. Check
   that history is cleared and stale actions cannot overwrite the external change.
4. Preview the example CSV with an additional invalid-date row. Verify its row
   number/reason, no changes before confirmation and only valid rows after it.
   Editing text or changing the account must disable confirmation until preview.
5. Download both PNG charts. Confirm the selected period matches their labels and
   check an empty category period produces the explanatory image.
6. Restart the backend without PFT_OPTIONAL_FEATURES. Core pages must work, the
   tools navigation must disappear and direct optional endpoints must return 404.

All five implementation parts are complete. Live browser acceptance remains a
manual check; automated component/API tests and generated-image inspection cover
the implemented behavior without modifying the user's running backend.
