# Task #25 – Recurring transactions: defense notes

FR-18 (Should). Owner: Isa Bilalli. Needs #14 (Transaction, `copy_for`) and #17 (factory);
uses #10's `Frequency` and #18's repository and store.

## The rule: `RecurringTransaction` (`pft/domain/recurring.py`)
- Fields: `template` (an Income or Expense), `frequency` (WEEKLY / MONTHLY / YEARLY), `start`,
  optional `end` (inclusive) and `last_run` (date of the last occurrence already added).
- A transfer cannot be a template (`InvalidTransferError`): copies would share one
  `transfer_id` and link unrelated pairs (#14's `Transfer.copy_for` already refuses).
- `end` before `start` → `InvalidDateError` with field `end_date`.

## Generators and `yield`
```python
def dates(self, until):
    limit = until if self.end is None else min(until, self.end)
    for index in count():
        day = occurrence_date(self.frequency, self.start, index)
        if day > limit:
            return
        if self.last_run is None or day > self.last_run:
            yield day
```
- A function with `yield` returns a generator. Nothing runs until someone asks for the next
  value; then the function runs to the next `yield` and pauses there, keeping its local
  variables (`index`, `day`).
- So the dates are produced **lazily**, one at a time. `itertools.count()` is infinite, but that
  is fine because the loop stops at `until`/`end`; `islice(rule.dates(date.max), 2)` only ever
  computes two dates (`test_dates_is_a_lazy_generator`).
- `occurrences(until, first_id=...)` is a second generator built on the first: it zips the
  dates with `count(first_id)` and yields `template.copy_for(day, new_id=...)`.
- `return` inside a generator ends it (raises `StopIteration` for the `for` loop).

## Date logic: count from the start, never chain
- #10's `Frequency.next_date` clamps: 31 Jan → 28 Feb. Chaining it gives 28 Feb → **28 Mar**,
  and every later month stays on the 28th (`test_chained_monthly_dates_drift_after_a_short_month`).
- `occurrence_date(frequency, start, n)` computes occurrence *n* directly from the start:
  - weekly: `start + n weeks`;
  - monthly: move *n* months, then clamp the day to that month's length;
  - yearly: move *n* years, then clamp (29 Feb → 28 Feb in a non-leap year, back to 29 in 2032).
- Result: 31 Jan → 28 Feb → 31 Mar → 30 Apr. The clamp is the same as #10's:
  `occurrence_date(f, start, 1) == f.next_date(start)` is tested for every frequency.
- Tested starts: 31 Jan (→ 28 Feb, 31 Mar), 28 Feb (stays on the 28th), 31 Mar (→ 30 Apr → 31 May),
  leap-year 31 Jan 2028 (→ 29 Feb).
- The plan's original sketch chained `next_date(day)`; step 6 of the task replaces that with the
  start-plus-index rule, which is what we built.

## No duplicates: `apply_due(ledger, today)`
1. Only dates **after `last_run`** are considered (the generator skips the rest).
2. Each candidate is also compared with what is already in the account (kind, amount, date,
   category, note — everything but the ID). A match is skipped. This covers a crash between
   saving the transactions and saving `last_run`.
3. `last_run` moves to each processed date, so the next run starts after it.

`apply_due` takes a `LedgerLike` Protocol (account, add_transaction, next_transaction_id), not
the `Ledger` class, so `pft.domain` does not import `pft.services` (dependency points inward).

## Saving `last_run` (restart safety)
- `Ledger` keeps the rules (`add_recurring`, `recurring`, `apply_recurring(today)`); closing an
  account drops its rules.
- `to_row()` / `from_row()` use exactly `RECURRING_COLUMNS` from #18, including `last_run`.
- All three repositories save the rules: `recurring.csv`, a `"recurring"` list in JSON, and a new
  `recurring` table in SQLite, written **in the same database transaction** as the accounts and
  transactions. So either the new items and the new `last_run` are both stored, or neither.
- `LedgerStore` applies due rules every time it loads the Ledger and saves at once if anything
  was added. A restart is just another load: nothing new is due, nothing is added.

## API (`pft/api/recurring.py`)
| Route | What it does |
|---|---|
| `POST /api/recurring` | Save a rule; add the occurrences already due. Returns `{rule, added}`. |
| `GET /api/recurring` | Saved rules, each with its next 3 dates. |
| `GET /api/recurring/preview` | Dates without saving: `due_count`, `due_now`, `upcoming`. |

Errors use `{code, message, field}`; fields are `frequency`, `start_date`, `end_date`, `amount`,
`kind`. Unknown account → 404.

## React (Transactions screen)
- The transaction form has a **Repeat** select (Does not repeat / Weekly / Monthly / Yearly). With a
  repeat chosen, Date becomes **Start date**, an optional **End date** appears, and
  **Upcoming occurrences** shows which items saving adds now and the next six dates. The dates
  come from the preview route, so React never does date arithmetic and cannot disagree with Python.
- Saving posts to `/api/recurring`; the list and a new **Recurring** card reload.
- Checked in the browser on a throwaway database (today 13 Nov 2026): a monthly rule from 31 Aug
  added 31 Aug, 30 Sep and 31 Oct; the next dates were 30 Nov, 31 Dec, 31 Jan, 28 Feb, 31 Mar,
  30 Apr. After two page reloads there were still exactly three items.

## Tests
- `tests/unit/test_recurring.py` (28 cases): month-end dates, `next_date` agreement, laziness, the
  plan's 1 Sep → 15 Nov = 3 items, running twice, a later run, end date, restart through SQLite,
  lost `last_run`, validation, row round-trip.
- `tests/integration/test_recurring_api.py` (16 cases): the routes, repeated loads/restarts,
  month end not shifted after reloads, preview, error shapes, closing an account, and all three
  repositories keeping rules and `last_run`.
- `frontend/tests/recurring.test.mjs` (5 cases): request body matches the Python model, preview
  query, error field mapping.

## Coordination with Florent (owner of #18 files) – draft, not sent
> Hi Florent, #25 needed rules to be saved, so with the team's OK I touched your files:
> `db.py` has a new `recurring` table (CREATE IF NOT EXISTS, so old databases get it on the next
> start); `repository.py` loads and saves rules in all three repositories (SQLite in the same
> transaction); `LedgerStore` now applies due rules on every load and saves if anything was
> added; `Ledger` holds the rules and `close_account` drops that account's rules. `recurring.csv`
> is now written on every save instead of only created once. All your tests still pass. Could you
> review those parts before I push? For #36, "apply due recurring transactions at start" is
> already covered by the store.

## Possible questions
- *Why not a cron job or a timer?* The app runs only when the user starts it. Applying on load
  catches up on anything missed while it was closed, and it is idempotent.
- *What if the rule changes amount later?* Not supported yet; a rule has no edit or delete route.
  An end date stops it. Editing/deleting rules is a follow-up.
- *Currency?* `RECURRING_COLUMNS` has no currency column, so rules use the default (EUR), like
  every account the app creates today.
