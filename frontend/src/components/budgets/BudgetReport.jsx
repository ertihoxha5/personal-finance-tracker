import { formatMonth, formatPercent } from '../../lib/format.js'
import { formatEUR } from '../../lib/money.js'

// Planned versus actual for one month (#31, FR-17). `report` is a useLoad result for
// fetchBudgetReport(month). Every number and status comes from the server's BudgetReport;
// the status is a word in its own column, so it never depends on colour.

const differenceText = ({ over, amount }) => `${formatEUR(amount)} ${over ? 'over' : 'under'}`

export default function BudgetReport({ month, report, thresholds }) {
  const { data, status, error, reload } = report

  let body
  if (status === 'error' && !data) {
    body = (
      <div className="state-message state-error" role="alert">
        <p>{error?.message}</p>
        <button type="button" className="button" onClick={reload}>
          Try again
        </button>
      </div>
    )
  } else if (!data) {
    body = (
      <div role="status">
        <span className="sr-only">Loading the budget report…</span>
        <div className="skeleton skeleton-block short" aria-hidden="true" />
      </div>
    )
  } else if (data.rows.length === 0) {
    body = (
      <p role="status">
        There are no budgets for {formatMonth(month)}, so there is nothing to compare. Set a budget above or choose
        another month.
      </p>
    )
  } else {
    body = (
      <div className="table-scroll" aria-busy={status === 'loading'}>
        <table className="data-table stack-narrow">
          <caption className="sr-only">Planned and actual spending per budget in {formatMonth(month)}</caption>
          <thead>
            <tr>
              <th scope="col">Category</th>
              <th scope="col" className="num">Planned</th>
              <th scope="col" className="num">Actual</th>
              <th scope="col" className="num">Difference</th>
              <th scope="col" className="num">Used</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.id}>
                <th scope="row">{row.name}</th>
                <td className="num" data-label="Planned">{formatEUR(row.planned)}</td>
                <td className="num" data-label="Actual">{formatEUR(row.actual)}</td>
                <td className="num" data-label="Difference">{differenceText(row.difference)}</td>
                <td className="num" data-label="Used">{formatPercent(row.usagePercent)}</td>
                <td data-label="Status">
                  <span className={`status-tag status-${row.status}`}>{row.statusLabel}</span>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row">Total</th>
              <td className="num" data-label="Planned">{formatEUR(data.totals.planned)}</td>
              <td className="num" data-label="Actual">{formatEUR(data.totals.actual)}</td>
              <td className="num" data-label="Difference">{differenceText(data.totals.difference)}</td>
              <td />
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
    )
  }

  return (
    <section className="card" aria-labelledby="budget-report-title">
      <h3 id="budget-report-title">Planned versus actual, {formatMonth(month)}</h3>
      {thresholds && (
        <p className="field-hint">
          Status: OK below {thresholds.warning}% of the plan, Warning from {thresholds.warning}%, Over from{' '}
          {thresholds.exceeded}%.
        </p>
      )}
      {body}
    </section>
  )
}
