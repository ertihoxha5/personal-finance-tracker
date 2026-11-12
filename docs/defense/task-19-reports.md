# Task #19 – Report base class and MonthlySummary: defense notes

## Template Method pattern
- `Report` is an abstract class (ABC). Its `build()` is the template method: it fixes the order
  `rows = collect()` then `summarize(rows)`. Subclasses fill in the two abstract steps and cannot
  change the order. `Report()` itself raises `TypeError`.
- Why it helps: #26 (CategoryReport) and #31 (TrendReport, BudgetReport) only write `collect` and
  `summarize`; the flow and the `ReportData` result type stay the same.
- `Report` is generic (`Report[MonthlySummaryData]`), so `build()` returns the right dataclass type
  for each report and mypy can check it.

## MonthlySummary(ledger, year, month)
- `collect()` returns one lazy stream: income and expense transactions of this month and the month
  before, using `apply_filters`, `any_of`, `by_kind` and `between` from #8. Transfers are not
  selected, so they cannot change a total.
- `summarize()` splits the stream into "this month" and "previous month", then builds the result.
- Result (`MonthlySummaryData`, a frozen dataclass): income, expenses, net, savings rate and a
  transaction count for each of the two months, every spending category largest first,
  `top_categories` (the first three, via `itertools.islice`) and the income, expenses and net
  change from last month.
- Category totals use `collections.Counter`, summed in integer cents so they are exact. Equal totals
  are ordered by category name, so the top three never depend on the input order.
- Savings rate = net / income x 100, rounded half-up to one decimal (`Decimal`, not float). No income
  gives `0.0`, not a division error; spending more than income gives a negative rate.
- A month with no transactions gives zeros and empty lists. January compares with December of the
  year before.

## API: GET /api/dashboard?month=YYYY-MM
- Everything is calculated in Python; React only displays. Leaving `month` out gives the latest month
  that has data (or the current month for an empty database). A bad month returns 422 with
  `{code: "invalid_date", message, field: "month"}`.
- Response: `summary`, `previous` (with `transaction_count`), `changes`, `top_categories`,
  `categories`, a five-month `trend` ending at the chosen month, `recent_transactions` (newest
  first, up to 8) and `available_months`. Amounts are decimal strings; `savings_rate` is a string
  such as `"25.0"`. Transfers are left out of every figure and list.

## React deliverable
- Dashboard now calls the API (`src/api/dashboard.js`, shared `src/api/http.js`). The month selector
  starts on the server's choice and lists the months that have data.
- Summary cards show income, expenses and net with the change versus the previous month (for example
  "+€200.00 vs October 2026"), the savings rate, and "No data for September 2026" when there is
  nothing to compare. A "Top spending categories" card lists the top three.
- Loading (skeleton), empty ("No transactions in November 2026") and error with Try again all exist.
  The Net worth card has its own retry.
- Checked in the browser with seeded data: figures matched a hand calculation, the month switch
  worked, stopping the backend showed the error state, and Try again recovered after a restart.

## Known limits
- Only EUR is supported on the dashboard; mixing currencies would raise `CurrencyMismatchError`.
- Each request loads the whole ledger and builds the report for six months (five for the trend, plus
  the previous one). That is fine at this data size.
- The CSV report export now writes only income, expenses, net and savings rate (not the count).
- `fixtures/dashboard.js` is kept only for the CSV export tests; the screen no longer uses it.
