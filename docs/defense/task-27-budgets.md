# Task #27 – Budgets and BudgetMonitor (Observer): defense notes

FR-15, FR-16. Owner: Isa Bilalli. Needs #11 (Ledger, events, `Observer` protocol) and #14
(`Expense`, `Income`, `Transfer`). Uses #18's repositories and store and #10's `BudgetError`.

Goal in one sentence: monthly budgets per category with automatic warnings, **without the
Ledger knowing anything about budgets**.

## `Budget` (`pft/domain/budget.py`)
- A frozen dataclass: `Budget(category, month, limit)`, e.g. `Budget(Category.FOOD, "2026-11",
  Money.of("200.00"))`. The month is text in the form `2026-11`, the same form the reports and
  budgets.csv use.
- Invalid input raises `BudgetError` (code `budget_error`) with `field` set to `month`, `limit`
  or `category`: the limit must be more than zero.
- `covers(tx)` is the one rule for what counts: an **`Expense`**, same category, same month,
  same currency as the limit. Income and transfers never count.
- `spent(ledger)` sums those expenses over `ledger.all_transactions()` (all accounts).
- `usage(ledger)` is spent as a percentage of the limit, a `Decimal` rounded **down** to one
  decimal: 165.00 / 200.00 → `82.5`. Rounding down means 199.99 of 200.00 shows 99.9%, never
  100%, before the limit is really reached.
- `is_exceeded(ledger)` is true at 100% or more. `level_reached(spent)` gives the highest level
  reached (`BUDGET_EXCEEDED`, `BUDGET_WARNING` or `None`).
- The thresholds are compared on exact amounts (`spent >= limit * level`), not on the rounded
  percentage.
- Constants, no magic numbers: `BUDGET_WARNING = Decimal("0.80")`, `BUDGET_EXCEEDED =
  Decimal("1.00")`, `BUDGET_LEVELS` (highest first). The API sends them to React as 80 and 100.
- The domain does not import the services layer: `spent` takes anything with
  `all_transactions()` (the `HasTransactions` protocol), like `LedgerLike` in #25.

## Observer pattern (`pft/services/budget_monitor.py`)
- #11 gave the Ledger `subscribe(observer)`, `unsubscribe(observer)` and `_notify(event)`.
  `Observer` is a `Protocol`: anything with `update(event)` fits, no base class needed.
- `BudgetMonitor` has `update(event)`, so `ledger.subscribe(monitor)` works. The Ledger calls
  `update` after every change; it has no idea the observer is about budgets.
- `update` ignores everything except `TransactionAdded` with an `Expense`. Then, for each budget
  that covers the expense, it checks whether a level was crossed.
- The monitor never prints. It calls the **callback** it was given with a `BudgetWarning`
  (category, month, level, usage; `message` is `"FOOD budget at 82%"`).
  - CLI: collects the warnings and prints `Warning: FOOD budget at 82%` after saving.
  - API: collects them in a list and returns them as JSON.
- Why this is better than `if` statements inside `Ledger.add_transaction`: budgets can be
  added, changed or removed without touching the Ledger, and the Ledger's tests need no budgets.
  `test_the_ledger_knows_nothing_about_budgets` checks that `ledger.py` never mentions them.
- If an observer raises, the Ledger logs it and carries on (#11), so a budget problem can never
  make adding a transaction fail.

## "Only once per level per month"
- A warning is sent only by the expense that **crosses** the level: `before = after − this
  expense`; warn when `before` is below the level and `after` is at or above it.
  - 150.00 → 165.00 of 200.00 crosses 80% → `FOOD budget at 82%`.
  - 165.00 → 175.00 crosses nothing → silent.
  - 165.00 → 200.00 crosses 100% → `FOOD budget at 100%`.
- This needs no saved state, so it also holds after a restart and in the API, where every
  request builds a new Ledger and a new monitor
  (`test_a_new_monitor_after_a_restart_does_not_repeat_old_warnings`).
- The monitor also keeps a set of `(category, month, level)` it already sent, so removing an
  expense and adding it again in one session does not repeat the warning.
- One expense that jumps from under 80% past 100% sends only the 100% warning.
- Each budget is its own (category, month), so December starts fresh.
- Why 82% and not 83% for 82.5: the message uses the whole percentage rounded down, as the plan's
  example shows.

## Separation of concerns
| Layer | File | Job |
|---|---|---|
| Domain | `pft/domain/budget.py` | What a budget is, what counts, the percentages, the constants |
| Service | `pft/services/budget_monitor.py` | When to warn (reacts to Ledger events) |
| Service | `pft/services/ledger.py` | Unchanged: accounts, transactions, notifying observers |
| Infrastructure | `repository.py`, `db.py` | Where budgets are stored |
| API | `pft/api/budgets.py`, `accounts.py` | JSON in and out |
| CLI | `pft/cli.py` | The only place that prints |
| React | `frontend/src/pages/Budgets.jsx` | Shows what the API calculated |

## Storage
- Budgets are stored **next to** the Ledger, not inside it: `Repository.load_budgets()` and
  `save_budgets(budgets)`. `save(ledger)` never touches them.
- CSV: `budgets.csv` with `BUDGET_COLUMNS` (category, month, limit, currency), written with
  `atomic_write`. JSON: the `"budgets"` list. SQLite: a `budgets` table, limit in integer cents,
  primary key (category, month), replaced inside one transaction.
- `Budget.to_row()` / `from_row()` round-trip; a bad stored row is a `DataImportError`.

## API
- `GET /api/budgets?month=2026-11` → `{month, thresholds: {warning: 80, exceeded: 100},
  budgets: [...], warnings: [...]}`. Each budget has `limit`, `spent`, `remaining`,
  `usage_percent` (decimal strings), `status` (`ok` / `warning` / `exceeded`) and `level`.
  `warnings` lists the budgets at or over a level right now. Default month: today's.
- `PUT /api/budgets` `{category, month, limit}` creates the budget or replaces its limit.
- `DELETE /api/budgets/{month}/{category}`.
- `POST /api/transactions` now also returns `warnings`: the levels this expense crossed (from
  the `BudgetMonitor`). All existing fields are unchanged.
- Errors keep the `{code, message, field}` shape: `budget_error` (limit, month),
  `invalid_amount` (limit), `invalid_category` (category).

## CLI
- `pft budget set food 200 [--month 2026-11]`, `pft budget list [--month 2026-11]`.
- `pft add expense 15 food` prints `Warning: FOOD budget at 82%` when a level is crossed.

## React (`/budgets`)
- Month input at the top; "Set a budget" form with category, month and limit inputs.
- One card per budget: spent of limit, what is left, a progress bar with the 80% mark, and the
  status in words ("82.5% used. Warning: 80% threshold passed."). The thresholds are named in
  text and come from the API, so nothing depends on colour and no number is typed in React.
- "Record spending" posts an expense; the page reloads the usage from the API and shows the
  warnings the API returned ("New budget warning"). A second list shows every budget that is
  over a threshold in the chosen month.
- React does no money arithmetic: totals, percentages and statuses are calculated in Python.

## Tests
- `tests/unit/test_budget.py` (13 cases): usage, what counts, rounding down, levels, validation,
  row round trip.
- `tests/unit/test_budget_monitor.py` (12 cases): the plan's scenario (200.00 / 150.00 + 15.00 →
  "FOOD budget at 82%"), income and transfers never warn, no repeat above 80%, 100% once, both
  levels in one expense, other categories/months, restart, remove and add again.
- `tests/integration/test_budgets_api.py` (20 cases): the routes, the same scenario through the
  API, error shapes, all three repositories, the CLI output.
- `frontend/tests/budgets.test.mjs` (6 cases): request bodies match the Python model, status text.

## Limits worth knowing
- Warnings are sent when an expense is **added** through `Ledger.add_transaction`. Editing an
  existing expense and expenses created by recurring rules (#25) change the usage shown on the
  Budgets screen, but do not send a "new" warning.
- A budget counts expenses in its own currency only (the app uses EUR everywhere).

## Likely questions
- *What is the Observer pattern?* A subject (Ledger) keeps a list of observers and tells them
  about events; it depends only on the `update(event)` method, not on who they are.
- *Why a Protocol instead of an abstract base class?* Structural typing: `BudgetMonitor` does
  not need to inherit from anything in the Ledger's module; mypy still checks the shape.
- *Why is the warning logic not in `Budget`?* `Budget` answers "how much is used?"; the monitor
  answers "did this event cross a level, and who should be told?". Two reasons to change, two
  classes.
- *Why Decimal constants?* `0.8` as a float is not exactly 0.8; `Decimal("0.80")` is, so 160.00
  of 200.00 is exactly at the level.
