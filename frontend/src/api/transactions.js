import { parseMoneyInput } from '../lib/money.js'

// Shared transaction adapter (#17): the one place that maps between the API's transaction
// DTO and what components use. Components never read `account_id` or work out a sign
// themselves; they call fromApi() on what the server sent and toApi() on what the form holds.
//
// The DTO follows pft.domain.transaction (CSV_COLUMNS): ids are integers, `amount` is an
// unsigned decimal string, and `kind` (plus `direction` for a transfer) gives the sign.
// Sign handling is done on the string, never through Number(), so no rounding creeps in.

const MINUS = '−'

// API field name -> component field name. Server errors use API names, so forms rename
// error fields through this map too.
export const API_TO_FORM_FIELD = Object.freeze({
  account_id: 'accountId',
  transfer_id: 'transferId',
})

// Every (kind, direction) pair the API sends, keyed `${kind}/${direction}` (empty direction
// for income and expense). Dictionary dispatch like TransactionFactory._CLASSES in Python:
// no switch on kind, and an unlisted pair is unknown rather than guessed.
//   formValue: the form's kind choice; label and sign: the row text; tone: an extra colour cue.
export const TRANSACTION_TYPES = Object.freeze({
  'income/': Object.freeze({ formValue: 'income', label: 'Income', sign: '+', tone: 'income' }),
  'expense/': Object.freeze({ formValue: 'expense', label: 'Expense', sign: MINUS, tone: 'expense' }),
  'transfer/out': Object.freeze({ formValue: 'transfer', label: 'Transfer out', sign: MINUS, tone: 'transfer' }),
  'transfer/in': Object.freeze({ formValue: 'transfer', label: 'Transfer in', sign: '+', tone: 'transfer' }),
})

const text = (value) => (value === null || value === undefined ? '' : String(value).trim())

// Look up how a kind/direction pair is shown. An unknown pair (a kind the API added, a
// transfer without a direction, an income with one) gets a readable label and message
// instead of throwing, so one odd row never breaks a whole list.
export function transactionType(kind, direction) {
  const key = `${text(kind)}/${text(direction)}`
  if (Object.hasOwn(TRANSACTION_TYPES, key)) return TRANSACTION_TYPES[key]
  const raw = text(direction) ? key : text(kind) || 'missing'
  return {
    formValue: null,
    label: 'Unknown type',
    sign: '',
    tone: 'unknown',
    raw,
    error: `Unknown transaction type "${raw}". Its amount is shown without a sign.`,
  }
}

// API DTO -> the object components use. `type` and `signedAmount` are derived once here.
export function fromApi(dto) {
  const source = dto ?? {}
  const type = transactionType(source.kind, source.direction)
  const amount = text(source.amount)
  return {
    id: source.id,
    accountId: source.account_id,
    kind: source.kind,
    direction: text(source.direction) || null,
    transferId: text(source.transfer_id) || null,
    amount,
    currency: source.currency ?? 'EUR',
    date: source.date,
    category: source.category,
    note: source.note ?? '',
    type,
    // Feed to formatEUR(..., { signed: true }): expense "64.50" -> "-64.50".
    signedAmount: type.sign === MINUS ? `-${amount}` : amount,
  }
}

// Form values -> request body for creating an income or expense. The amount is normalised
// here ("12,5" -> "12.50"); ids are integers, as in the Python domain; enums are their API
// values. Totals and transfer pairs are the server's job.
export function toApi({ kind, accountId, amount, date, category, note }) {
  const parsed = parseMoneyInput(text(amount))
  return {
    kind,
    account_id: Number.parseInt(accountId, 10),
    // An amount the form should have rejected is sent as typed, so the server's
    // InvalidAmountError reaches the user instead of a silent change.
    amount: parsed.value ?? text(amount),
    date,
    category,
    note: text(note),
  }
}
