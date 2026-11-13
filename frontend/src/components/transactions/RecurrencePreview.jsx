import { previewRecurring, recurringPreviewQuery } from '../../api/recurring.js'
import { useDebounced } from '../../hooks/useDebounced.js'
import { useLoad } from '../../hooks/useLoad.js'
import { formatDate } from '../../lib/format.js'
import { isoDate } from '../../lib/transactions.js'

// Shows which dates a recurring rule will use before it is saved (#25). The dates come from
// the server, so the preview follows exactly the month-end rule that saving will use.
export default function RecurrencePreview({ frequency, startDate, endDate }) {
  const ready = isoDate(startDate) === null && (!endDate || isoDate(endDate) === null)
  const query = useDebounced(ready ? recurringPreviewQuery({ frequency, startDate, endDate }) : '')
  const preview = useLoad(
    () => (query ? previewRecurring({ frequency, startDate, endDate }) : Promise.resolve(null)),
    query,
  )

  if (!ready) return null
  let body
  if (preview.status === 'error') {
    body = <p className="field-error">{preview.error?.message}</p>
  } else if (!preview.data) {
    body = <p className="field-hint">Working out the dates…</p>
  } else {
    const { due_count: dueCount, due_now: dueNow, upcoming } = preview.data
    body = (
      <>
        {dueCount > 0 && (
          <p>
            Saving adds {dueCount} {dueCount === 1 ? 'item' : 'items'} now:{' '}
            {dueNow.map(formatDate).join(', ')}
            {dueCount > dueNow.length ? ', …' : ''}
          </p>
        )}
        {upcoming.length > 0 ? (
          <>
            <p>Next:</p>
            <ol className="upcoming-dates">
              {upcoming.map((day) => (
                <li key={day}>
                  <time dateTime={day}>{formatDate(day)}</time>
                </li>
              ))}
            </ol>
          </>
        ) : (
          <p>No more dates after today.</p>
        )}
      </>
    )
  }

  return (
    <section className="recurrence-preview" aria-label="Upcoming occurrences" aria-live="polite">
      <h4>Upcoming occurrences</h4>
      {body}
    </section>
  )
}
