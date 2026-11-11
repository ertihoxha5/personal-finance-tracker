import { formatEUR, formatPercent } from '../../lib/format.js'

export default function SummaryCards({ summary }) {
  return (
    <ul className="summary-cards" aria-label="Monthly summary">
      <li className="card summary-card">
        <h3 className="summary-label">Income</h3>
        <p className="summary-value">{formatEUR(summary.income)}</p>
      </li>
      <li className="card summary-card">
        <h3 className="summary-label">Expenses</h3>
        <p className="summary-value">{formatEUR(summary.expenses)}</p>
      </li>
      <li className="card summary-card">
        <h3 className="summary-label">Net cash flow</h3>
        <p className="summary-value">{formatEUR(summary.net, { signed: true })}</p>
        <p className="summary-meta">Savings rate {formatPercent(summary.savingsRate)}</p>
      </li>
    </ul>
  )
}
