import { request } from './http.js'
import { toApi } from './transactions.js'

// Recurring rules client (#25): talks to pft/api/recurring.py. The server works out every
// date (month ends count from the start date, so 31 Jan -> 28 Feb -> 31 Mar), adds the
// occurrences that are already due when a rule is saved, and adds later ones as they fall
// due. Loading the same data again never adds a duplicate. React only shows the dates.

// Server field names -> the transaction form's field names.
export const RECURRING_FIELD_TO_FORM = Object.freeze({
  start_date: 'date',
  end_date: 'endDate',
  frequency: 'frequency',
})

// Form values -> request body. The transaction's date is the rule's start date.
export function toRecurringApi(values) {
  const { date, ...transaction } = toApi(values)
  const endDate = String(values.endDate ?? '').trim()
  return { ...transaction, frequency: values.frequency, start_date: date, end_date: endDate || null }
}

// Resolves { rule, added }: the saved rule (with its next dates) and the items added now.
export function createRecurring(body) {
  return request('/recurring', { method: 'POST', body })
}

export function listRecurring() {
  return request('/recurring')
}

// Dates a rule would produce, without saving: { due_count, due_now, upcoming }.
export function recurringPreviewQuery({ frequency, startDate, endDate = '', count = 6 }) {
  const query = new URLSearchParams({ frequency, start_date: startDate, count: String(count) })
  if (endDate) query.set('end_date', endDate)
  return query.toString()
}

export function previewRecurring(options) {
  return request(`/recurring/preview?${recurringPreviewQuery(options)}`)
}
