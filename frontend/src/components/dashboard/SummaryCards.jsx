import { formatMonth, formatPercent } from '../../lib/format.js'
import { formatEUR } from '../../lib/money.js'

// "+€300.00 vs October 2026". The sign and words carry the meaning, not colour. When last
// month had no transactions there is nothing to compare with, so the card says so.
function Comparison({ change, previous }) {
  const label = formatMonth(previous.month)
  if (!previous.hasData) return <p className="summary-meta">No data for {label}</p>
  return (
    <p className="summary-meta">
      {formatEUR(change, { signed: true })} vs {label}
    </p>
  )
}

export default function SummaryCards({ summary, previous }) {
  return (
    <ul className="summary-cards" aria-label="Monthly summary">
      <li className="card summary-card">
        <h3 className="summary-label">Income</h3>
        <p className="summary-value">{formatEUR(summary.income)}</p>
        <Comparison change={previous.changes.income} previous={previous} />
      </li>
      <li className="card summary-card">
        <h3 className="summary-label">Expenses</h3>
        <p className="summary-value">{formatEUR(summary.expenses)}</p>
        <Comparison change={previous.changes.expenses} previous={previous} />
      </li>
      <li className="card summary-card">
        <h3 className="summary-label">Net cash flow</h3>
        <p className="summary-value">{formatEUR(summary.net, { signed: true })}</p>
        <p className="summary-meta">Savings rate {formatPercent(summary.savingsRate)}</p>
        <Comparison change={previous.changes.net} previous={previous} />
      </li>
    </ul>
  )
}
