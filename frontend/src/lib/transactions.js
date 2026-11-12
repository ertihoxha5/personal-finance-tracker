// Transaction helpers shared by the form and the row display (#14).
//
// Transactions travel the way pft.domain.transaction stores them: `amount` is an
// unsigned decimal string and `kind` (plus `direction` for a transfer) gives the sign.
// Sign handling is done on the string, never through Number(), so no rounding creeps in.

const MINUS = '−'

// How a row presents its kind. The text label and the sign carry the meaning on their
// own; `tone` is only an extra hint for colour, so nothing relies on colour alone.
//   kindDisplay({ kind: 'expense' }) -> { label: 'Expense', sign: '−', tone: 'expense' }
export function kindDisplay(transaction) {
  switch (transaction?.kind) {
    case 'income':
      return { label: 'Income', sign: '+', tone: 'income' }
    case 'expense':
      return { label: 'Expense', sign: MINUS, tone: 'expense' }
    case 'transfer':
      return transaction.direction === 'in'
        ? { label: 'Transfer in', sign: '+', tone: 'transfer' }
        : transaction.direction === 'out'
          ? { label: 'Transfer out', sign: MINUS, tone: 'transfer' }
          : { label: 'Transfer', sign: '', tone: 'transfer' }
    default:
      return { label: 'Unknown', sign: '', tone: 'unknown' }
  }
}

// The balance effect as a signed decimal string: expense "64.50" -> "-64.50".
// Feed it to formatEUR(..., { signed: true }) for display.
export function signedAmount(transaction) {
  const amount = String(transaction.amount ?? '')
  return kindDisplay(transaction).sign === MINUS ? `-${amount}` : amount
}

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

// Form values -> request body. `amount` must already be normalised by parseMoneyInput
// ("12.50"); ids are integers, as in the Python domain; enums are their API values.
export function toDto({ kind, accountId, amount, date, category, note }) {
  return {
    kind,
    account_id: Number.parseInt(accountId, 10),
    amount,
    date,
    category,
    note: (note ?? '').trim(),
  }
}

