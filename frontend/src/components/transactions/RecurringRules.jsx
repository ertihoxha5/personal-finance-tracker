import { formatDate } from '../../lib/format.js'
import { categoryLabel, frequencyLabel, kindLabel } from '../../lib/labels.js'
import { formatEUR } from '../../lib/money.js'

// Saved recurring rules with their next dates (#25). `rules` is the GET /api/recurring list.
export default function RecurringRules({ rules, accountName }) {
  if (!rules || rules.length === 0) return null
  return (
    <section className="card" aria-labelledby="recurring-title">
      <h3 id="recurring-title">Recurring</h3>
      <ul className="recurring-list">
        {rules.map((rule, index) => (
          <li key={`${rule.account_id}-${rule.start_date}-${index}`}>
            <strong>
              {frequencyLabel(rule.frequency)} {kindLabel(rule.kind).toLowerCase()}
            </strong>{' '}
            {formatEUR(rule.amount)} · {rule.note || categoryLabel(rule.category)} · {accountName(rule.account_id)}
            <br />
            <span className="field-hint">
              From {formatDate(rule.start_date)}
              {rule.end_date ? ` to ${formatDate(rule.end_date)}` : ''}.{' '}
              {rule.upcoming.length > 0
                ? `Next: ${rule.upcoming.map(formatDate).join(', ')}`
                : 'No more dates.'}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
