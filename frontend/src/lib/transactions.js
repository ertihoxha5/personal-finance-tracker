// Date helpers for the transaction form (#14). Mapping between the API DTO and
// component values (kind/direction labels, signs, field names) lives in
// api/transactions.js (#17).

// Today's date as ISO "YYYY-MM-DD" in the user's own time zone. toISOString() would
// give the UTC date, which is yesterday or tomorrow near midnight.
export function todayISO(now = new Date()) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/

// Rule for useFormValidation: a real calendar date in ISO form ("2026-02-30" fails).
export function isoDate(text) {
  if (typeof text !== 'string' || text.trim() === '') return 'Enter a date.'
  const match = ISO_DATE.exec(text.trim())
  if (!match) return 'Enter a date like 2026-11-15.'
  const [, y, m, d] = match.map((part) => Number.parseInt(part, 10))
  const probe = new Date(Date.UTC(y, m - 1, d))
  if (probe.getUTCFullYear() !== y || probe.getUTCMonth() !== m - 1 || probe.getUTCDate() !== d) {
    return 'That date does not exist.'
  }
  return null
}
