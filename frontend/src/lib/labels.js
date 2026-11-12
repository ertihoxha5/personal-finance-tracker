// Readable labels for the Python enums in pft/domain/category.py (#10).
// Keys must match the API values exactly: they are the lowercase StrEnum values,
// so 'food' here is Category.FOOD there. Adding a value in Python means adding it here.

export const CATEGORY_LABELS = Object.freeze({
  salary: 'Salary',
  food: 'Food',
  rent: 'Rent',
  bills: 'Bills',
  transport: 'Transport',
  fun: 'Fun',
  health: 'Health',
  education: 'Education',
  other: 'Other',
})

export const KIND_LABELS = Object.freeze({
  income: 'Income',
  expense: 'Expense',
  transfer: 'Transfer',
})

export const DIRECTION_LABELS = Object.freeze({
  out: 'Out',
  in: 'In',
})

export const ACCOUNT_TYPE_LABELS = Object.freeze({
  cash: 'Cash',
  bank: 'Bank',
  card: 'Card',
  savings: 'Savings',
})

export const FREQUENCY_LABELS = Object.freeze({
  weekly: 'Weekly',
  monthly: 'Monthly',
  yearly: 'Yearly',
})

// A value the frontend does not know yet (e.g. the API added one) still reads
// sensibly: 'credit_line' -> 'Credit line'. Missing values show as 'Unknown'.
export function fallbackLabel(value) {
  if (value === null || value === undefined || String(value).trim() === '') return 'Unknown'
  const words = String(value).trim().replace(/[_-]+/g, ' ').toLowerCase()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

const lookup = (labels) => (value) =>
  Object.hasOwn(labels, value) ? labels[value] : fallbackLabel(value)

export const categoryLabel = lookup(CATEGORY_LABELS)
export const kindLabel = lookup(KIND_LABELS)
export const directionLabel = lookup(DIRECTION_LABELS)
export const accountTypeLabel = lookup(ACCOUNT_TYPE_LABELS)
export const frequencyLabel = lookup(FREQUENCY_LABELS)

// [{ value, label }] in API order, for <select> options.
export const toOptions = (labels) => Object.entries(labels).map(([value, label]) => ({ value, label }))
