// Display-only formatting. Amounts arrive as decimal strings and are converted with
// Number() here, at render time; no arithmetic on money happens in React.
// #06 replaces this with the shared formatter and money input.

const eur = new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR' })
const eurSigned = new Intl.NumberFormat('en-IE', {
  style: 'currency',
  currency: 'EUR',
  signDisplay: 'exceptZero',
})

export function formatEUR(amount, { signed = false } = {}) {
  return (signed ? eurSigned : eur).format(Number(amount))
}

export function formatPercent(value) {
  return value === null || value === undefined ? '—' : `${value}%`
}

function monthDate(isoMonth) {
  const [year, month] = isoMonth.split('-')
  return new Date(Date.UTC(Number(year), Number(month) - 1, 1))
}

const longMonth = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' })
const shortMonth = new Intl.DateTimeFormat('en-GB', { month: 'short', timeZone: 'UTC' })
const dayFormat = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  timeZone: 'UTC',
})

export const formatMonth = (isoMonth) => longMonth.format(monthDate(isoMonth))
export const formatShortMonth = (isoMonth) => shortMonth.format(monthDate(isoMonth))
export const formatDate = (isoDate) => dayFormat.format(new Date(`${isoDate}T00:00:00Z`))
