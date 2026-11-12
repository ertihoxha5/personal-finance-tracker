import { parseMoneyInput } from './money.js'

export const emptyFilters = () => ({
  categories: [], kind: '', account: '', start: '', end: '', minimum: '', maximum: '', note: '',
  sortKey: 'date', sortDirection: 'asc',
})

// Compare normalized decimal strings using integer cents, without float rounding.
const cents = (amount) => BigInt(amount.replace('.', ''))

export function validateFilters(filters) {
  const errors = {}
  if (filters.start && filters.end && filters.start > filters.end) {
    errors.end = 'End date must be on or after start date.'
  }
  const minimum = parseMoneyInput(filters.minimum)
  const maximum = parseMoneyInput(filters.maximum)
  if (minimum.error) errors.minimum = minimum.error
  if (maximum.error) errors.maximum = maximum.error
  if (minimum.value !== null && maximum.value !== null && cents(minimum.value) > cents(maximum.value)) {
    errors.maximum = 'Maximum amount must be at least the minimum.'
  }
  return { errors, minimum: minimum.value, maximum: maximum.value }
}

// Fixture preview only. Backend integration should delegate filtering to #08's
// Python predicates; this helper never calculates balances or report totals.
export function filterTransactions(items, filters) {
  const { errors, minimum, maximum } = validateFilters(filters)
  if (Object.keys(errors).length) return []
  const note = filters.note.trim().toLocaleLowerCase('en')
  return items.filter((item) => (
    (!filters.categories.length || filters.categories.includes(item.category)) &&
    (!filters.kind || item.kind === filters.kind) &&
    (!filters.account || String(item.account_id) === filters.account) &&
    (!filters.start || item.date >= filters.start) &&
    (!filters.end || item.date <= filters.end) &&
    (minimum === null || cents(item.amount) >= cents(minimum)) &&
    (maximum === null || cents(item.amount) <= cents(maximum)) &&
    (!note || item.note.toLocaleLowerCase('en').includes(note))
  ))
}

const SORT_VALUES = {
  date: (transaction) => transaction.date,
  amount: (transaction) => cents(transaction.amount),
  category: (transaction) => transaction.category,
}

export function sortTransactions(items, key = 'date', reverse = false) {
  if (!Object.hasOwn(SORT_VALUES, key)) {
    throw new RangeError(`Unknown sort key '${key}'; choose one of: date, amount, category.`)
  }
  const valueOf = SORT_VALUES[key]
  return [...items].sort((left, right) => {
    const leftValue = valueOf(left)
    const rightValue = valueOf(right)
    let comparison = 0
    if (leftValue < rightValue) comparison = -1
    if (leftValue > rightValue) comparison = 1
    return reverse ? -comparison : comparison
  })
}

// The same pipeline feeds the table and its order tests. Older filter objects
// without sort settings use the Python sort_transactions defaults.
export function selectTransactions(items, filters) {
  return sortTransactions(
    filterTransactions(items, filters),
    filters.sortKey ?? 'date',
    filters.sortDirection === 'desc',
  )
}
