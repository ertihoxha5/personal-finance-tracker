# Task #31 – TrendReport and BudgetReport: defense notes

FR-10, FR-17. Owner: Isa Bilalli. Needs #19 (Florent's `Report` base class) and #27 (`Budget`,
the 80% and 100% limits).

Goal in one sentence: two more reports that reuse the base class, each writing only
`collect()` and `summarize()`.

## Template Method
```python
class Report(ABC, Generic[D]):
    def build(self) -> D:
        rows = self.collect()
        return self.summarize(rows)
```
- `build()` is the template method: it fixes the order of the steps. `collect()` and
  `summarize()` are abstract; each report fills them in.
- `TrendReport` and `BudgetReport` do **not** define `build()`. They inherit it, so there are
  now four reports (monthly, category, trend, budget) and still one `build()`.
- Proof in the tests: `"build" not in vars(TrendReport)` and `TrendReport.build is
  Report.build` (same for `BudgetReport`).
- Why not copy `build()` into each report? If the order or a shared step ever changes (for
  example logging, or checking the rows), it changes in one place for every report.
- `Report[D]` is generic: `TrendReport(Report[TrendReportData])` tells mypy that `build()`
  returns a `TrendReportData`.

## TrendReport(ledger, months, year, month)
- "The last N months" ending with (year, month). The constructor works out the N months once,
  oldest first, by stepping back with `previous_month` (so December → January of the year
  before works).
- `collect()`: income and expenses from the first day of the first month to the last day of the
  last month, with the #8 filters (`any_of(by_kind(INCOME), by_kind(EXPENSE))`, `between`).
  Transfers are left out, as in every report.
- `summarize()`: two `Counter`s keyed by (year, month), **started at 0 for every month**, so a
  month without data still gets its row. Sums are integer cents, never floats.
- Result: `TrendReportData.months`, a tuple of `MonthTotals(year, month, income, expenses,
  net)`. N = 6 gives exactly 6 rows in date order.
- N must be 1 to `MAX_TREND_MONTHS` (120); a range that starts before 1900 is an
  `InvalidDateError`, like the other reports.

## BudgetReport(ledger, budgets, month)
- The budgets are passed in: the Ledger does not know about budgets (#27).
- `collect()`: the month's expenses. `summarize()`: for each budget of that month, ordered by
  category name, a `BudgetLine`:
  - `planned` = the budget's limit, `actual` = what was spent, `difference` = planned − actual
    (negative when overspent), `usage` = percent used (rounded down to one decimal),
  - `status`: `BudgetStatus.OK`, `WARNING` or `OVER`.
- Plus totals for the month: planned, actual, difference.
- A month without budgets gives no lines and zero totals, not an error.

## Statuses match the 80% and 100% limits
- The report does not have its own numbers. It asks `budget.level_reached(actual)` (#27), which
  uses `BUDGET_WARNING = Decimal("0.80")` and `BUDGET_EXCEEDED = Decimal("1.00")`, and maps the
  answer with a dictionary: `None → OK`, `BUDGET_WARNING → WARNING`, `BUDGET_EXCEEDED → OVER`.
- So the report and the warnings of the `BudgetMonitor` can never disagree.
- Limit 200.00: 159.99 → OK, 160.00 → WARNING, 199.99 → WARNING, 200.00 → OVER (tested).
- `BudgetStatus` is a `StrEnum` with lowercase values (`"ok"`, `"warning"`, `"over"`), like the
  other enums (#10); `BUDGET_STATUS_LABELS` in `labels.js` is keyed by exactly these values.

## Code reuse (what was not written again)
- `Report.build()` (#19).
- The filters `apply_filters`, `by_kind`, `between`, `any_of` (#8).
- `Budget.covers`, `Budget.level_reached`, `Budget.percent_of` and the two constants (#27).
- `previous_month`, `parse_month`, `_last_day`, `_cents`, `_from_cents` already in `reports.py`.
- The Dashboard's trend now comes from `TrendReport` instead of building five
  `MonthlySummary` reports in a loop. The `/api/dashboard` response is unchanged (tested).

## API
- `GET /api/reports/budget?month=2026-11` → `{month, currency, rows: [{category, planned,
  actual, difference, usage_percent, status}], totals: {planned, actual, difference}}`.
  Default month: today's. Bad month → 422 `invalid_date`, field `month`.
- `GET /api/reports/trend?months=6&end=2026-11` → `{months: [{month, income, expenses,
  net}]}`. Defaults: 6 months, ending this month. `months` outside 1–120 or a bad `end` → 422.
- Amounts and percentages are decimal strings; nothing is calculated in React.

## React (Budgets screen)
- New card "Planned versus actual, <month>": a table with Category, Planned, Actual,
  Difference ("€35.00 under" / "€10.00 over"), Used and Status, and a Total row.
- It uses the page's month filter and reloads after a budget is saved or removed and after an
  expense is added.
- Empty result: "There are no budgets for December 2026, so there is nothing to compare."
  Loading and server errors (with Try again) are handled.
- The status is a word in its own column; colour and border style are only extra cues.
- Trend visualization: kept on the Dashboard ("Income vs expenses"), now fed by `TrendReport`.
  It was not added a second time to the Budgets screen.

## Tests
- `tests/unit/test_trend_budget_reports.py` (22 cases): 6 rows in date order, zero months, year
  boundary, transfers left out, agreement with `MonthlySummary`, the status limits, negative
  difference, empty month, and `build()` inherited, not copied.
- `tests/integration/test_budget_trend_api.py` (12 cases): both routes, defaults, empty month,
  error shapes, and the Dashboard trend unchanged.
- `frontend/tests/budgetReport.test.mjs` (6 cases): month filter in the request, empty result,
  labels keyed by the Python enum values.

## Limits worth knowing
- `/api/budgets` (#27) calls the 100% state `"exceeded"`; this report calls it `"over"`, the
  word the plan uses for the report. Same limit, two names.
- Spending in a category without a budget is not in the report (there is nothing planned to
  compare it with).
- There is no CLI command for these two reports yet; `cli.py` belongs to #36.

## Likely questions
- *Template Method vs Strategy?* Template Method uses inheritance: the base class owns the
  algorithm and subclasses fill in steps. Strategy (the exporters, #24) uses composition: the
  whole algorithm is swapped as an object.
- *Why does `collect()` return an iterable and not a list?* The filters are lazy generators;
  `summarize()` reads them once. `BudgetReport` turns them into a list because it goes over the
  expenses once per budget.
- *Why are months without data a requirement?* A chart or table with missing months would
  silently close the gap and mislead; a zero row keeps the time axis honest.
