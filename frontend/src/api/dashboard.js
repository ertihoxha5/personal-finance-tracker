import { DASHBOARD_FIXTURES, FIXTURE_MONTHS, emptyDashboard } from '../fixtures/dashboard.js'

export const DEFAULT_MONTH = FIXTURE_MONTHS[FIXTURE_MONTHS.length - 1]

const FIXTURE_DELAY_MS = 300

// Stage B data source: serves fixtures. #19 replaces this body with
// fetch(`/api/dashboard?month=${month}`) and keeps the same resolved shape.
//
// Append ?state=loading | empty | error to the page URL to preview the other UI states.
export function fetchDashboard(month) {
  const state = new URLSearchParams(window.location.search).get('state')
  if (state === 'loading') {
    return new Promise(() => {})
  }

  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (state === 'error') {
        reject(new Error('The dashboard could not be loaded.'))
      } else if (state === 'empty') {
        resolve(emptyDashboard(month))
      } else if (DASHBOARD_FIXTURES[month]) {
        resolve(DASHBOARD_FIXTURES[month])
      } else {
        reject(new Error(`No data for ${month}.`))
      }
    }, FIXTURE_DELAY_MS)
  })
}
