import { budgetStatusLabel, categoryLabel } from '../lib/labels.js'
import { request } from './http.js'

// Budget report client (#31): GET /api/reports/budget?month=YYYY-MM, built by BudgetReport in
// pft/services/reports.py. Planned, actual, difference, the percentage and the status are all
// calculated by the server; this file only attaches display labels.

// "-10.00" -> { over: true, amount: "10.00" }. Done on the string, never through Number().
export function splitDifference(difference) {
  const text = String(difference ?? '')
  return text.startsWith('-') ? { over: true, amount: text.slice(1) } : { over: false, amount: text }
}

const toRow = (row) => ({
  id: row.category,
  name: categoryLabel(row.category),
  planned: row.planned,
  actual: row.actual,
  difference: splitDifference(row.difference),
  usagePercent: row.usage_percent,
  status: row.status,
  statusLabel: budgetStatusLabel(row.status),
})

// Resolves { month, rows, totals }. A month without budgets resolves with rows: [].
export async function fetchBudgetReport(month) {
  const dto = await request(`/reports/budget?${new URLSearchParams({ month })}`)
  return {
    month: dto.month,
    rows: dto.rows.map(toRow),
    totals: {
      planned: dto.totals.planned,
      actual: dto.totals.actual,
      difference: splitDifference(dto.totals.difference),
    },
  }
}
