// Shared money helpers. Amounts travel as decimal strings ("1250.00"), exactly as the
// API sends them. Number() is used only inside formatEUR, for display; parsing and
// normalising user input is done on the string so no rounding can creep in.

const LOCALE = 'en-IE'
const MINUS = '−'
const MAX_INTEGER_DIGITS = 12

const plain = new Intl.NumberFormat(LOCALE, { style: 'currency', currency: 'EUR' })
const signedFormat = new Intl.NumberFormat(LOCALE, {
  style: 'currency',
  currency: 'EUR',
  signDisplay: 'exceptZero',
})

// formatEUR("-1250.5") -> "−€1,250.50". Zero (including "-0.00") is always "€0.00".
// With { signed: true } positive amounts get a "+" too, for income/expense lists.
export function formatEUR(amount, { signed = false } = {}) {
  if (typeof amount !== 'string' && typeof amount !== 'number') return '—'
  const value = Number(amount)
  if (!Number.isFinite(value)) return '—'
  const nonNegativeZero = value === 0 ? 0 : value
  return (signed ? signedFormat : plain).format(nonNegativeZero).replace('-', MINUS)
}

const INPUT_PATTERN = /^(\d*)(?:[.,](\d*))?$/

// Parse what a user typed into a normalised decimal string.
// Accepts "12", "12.5", "12,50", ".5" and "12."; rejects signs, letters,
// thousands separators and more than two decimals.
// Returns { value: "12.50" | null, error: string | null }.
export function parseMoneyInput(text) {
  const trimmed = text.trim()
  if (trimmed === '') return { value: null, error: null }

  const match = INPUT_PATTERN.exec(trimmed)
  if (!match || (match[1] === '' && (match[2] ?? '') === '')) {
    return { value: null, error: 'Enter an amount like 12.50.' }
  }

  const [, integerDigits, fractionDigits = ''] = match
  if (fractionDigits.length > 2) {
    return { value: null, error: 'Use at most 2 decimal places.' }
  }

  const integerPart = integerDigits.replace(/^0+(?=\d)/, '') || '0'
  if (integerPart.length > MAX_INTEGER_DIGITS) {
    return { value: null, error: 'That amount is too large.' }
  }

  return { value: `${integerPart}.${fractionDigits.padEnd(2, '0')}`, error: null }
}
