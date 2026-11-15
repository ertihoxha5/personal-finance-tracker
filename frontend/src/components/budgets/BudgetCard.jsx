import { barPercent, statusText } from '../../api/budgets.js'
import { formatPercent } from '../../lib/format.js'
import { categoryLabel } from '../../lib/labels.js'
import { formatEUR } from '../../lib/money.js'

// One budget with its progress (#27). Every number comes from the API. The status is
// written out in words and the two thresholds are named under the bar, so nothing depends
// on colour alone.
export default function BudgetCard({ budget, thresholds, onDelete, busy }) {
  const label = categoryLabel(budget.category)
  const over = budget.remaining.startsWith('-')

  return (
    <li className={`card budget-card budget-${budget.status}`}>
      <div className="page-header">
        <h3>{label}</h3>
        <button
          type="button"
          className="button button-secondary button-small"
          onClick={() => onDelete(budget)}
          disabled={busy}
          aria-label={`Remove the ${label} budget`}
        >
          Remove
        </button>
      </div>

      <p className="budget-amounts">
        <strong>{formatEUR(budget.spent)}</strong> spent of {formatEUR(budget.limit)} ·{' '}
        {over ? `${formatEUR(budget.remaining.slice(1))} over the limit` : `${formatEUR(budget.remaining)} left`}
      </p>

      <div
        className="budget-bar"
        role="progressbar"
        aria-label={`${label} budget used`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={barPercent(budget.usage_percent)}
        aria-valuetext={`${formatPercent(budget.usage_percent)} used. ${statusText(budget, thresholds)}`}
      >
        <div className="budget-bar-fill" style={{ width: `${barPercent(budget.usage_percent)}%` }} />
        <span className="budget-bar-mark" style={{ left: `${thresholds.warning}%` }} aria-hidden="true" />
      </div>
      <div className="budget-scale" aria-hidden="true">
        <span style={{ left: `${thresholds.warning}%` }}>{thresholds.warning}% warning</span>
        <span className="budget-scale-end">{thresholds.exceeded}% limit</span>
      </div>

      <p className="budget-status">
        <strong>{formatPercent(budget.usage_percent)} used.</strong> {statusText(budget, thresholds)}.
      </p>
    </li>
  )
}
