# Task #26 – CategoryReport: defense notes

## Inheritance and Template Method
- `CategoryReport(Report[CategoryReportData])` inherits `build()` from `Report` (#19) and writes only
  the two steps: `collect()` and `summarize()`. It does not override `build()`, so the order
  (collect, then summarize) cannot change. A unit test checks this.
- `collect()` is lazy: expenses between `start` and `end` (both inclusive), using `apply_filters`,
  `by_kind` and `between` from #8. Income and transfers are not spending.
- `summarize()` adds amounts per category in integer cents (`Counter`), sorts largest first (ties by
  category name), hides categories with no spending, and returns a frozen `CategoryReportData`.

## Percentages add up to 100.0
- Rounding each share alone breaks the sum (three equal thirds give 33.3 x 3 = 99.9; seven equal
  sevenths give 14.3 x 7 = 100.1). `_share_in_tenths` uses the largest remainder method: every share
  is rounded down to a tenth of a percent in integer arithmetic, then the missing tenths go to the
  shares with the largest remainders. The sum is exactly 100.0, so the "±0.1" check always holds.
- No spending: total `0.00`, no categories, no division by zero.
- A reversed range raises `InvalidDateError` (field `end`).

## API: GET /api/reports/categories?start=YYYY-MM-DD&end=YYYY-MM-DD
- New route; `/api/dashboard` is unchanged. Response: `start`, `end`, `currency`, `total`,
  `categories[{category, total, percent}]`. Amounts and percentages are strings.
- Bad, missing or reversed dates return 422 with `{code: "invalid_date", message, field}`.

## React deliverable
- `CategoryBreakdown` on the Dashboard now has From/To date inputs. It starts on the selected
  month and follows the month picker, but any range (one day, a full year) can be typed.
- Shows a bar chart (hidden from screen readers) plus an accessible table with Category, Spent,
  Share and a Total row. Empty periods show "No spending between ...". A reversed range shows an
  error and sends no request. Loading and server errors (with Try again) are handled.
- All numbers come from the server; React only formats them.

## Tests
- `tests/unit/test_category_report.py` (12 cases): ordering, ties, hidden categories, percentage
  sums, one day, full year with boundaries, empty period, reversed range, Template Method.
- `tests/integration/test_reports_api.py` (7 cases): month range, empty period, bad dates.
