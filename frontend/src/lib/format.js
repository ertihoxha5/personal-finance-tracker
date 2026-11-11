// Display-only formatting for percentages and dates. Money formatting lives in money.js.

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
