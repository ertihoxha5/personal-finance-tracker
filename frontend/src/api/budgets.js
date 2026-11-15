import { parseMoneyInput } from '../lib/money.js'
import { request } from './http.js'

// Budgets API client (#27): talks to pft/api/budgets.py. The server stores the budgets and
// works out everything from the Ledger's expenses: spent, remaining, usage_percent, the
// status ('ok' | 'warning' | 'exceeded') and the warnings. React only shows them; it never
// adds amounts or compares against a threshold itself.

// GET /api/budgets?month=YYYY-MM -> { month, thresholds: { warning, exceeded }, budgets, warnings }
export function listBudgets(month) {
  return request(`/budgets?${new URLSearchParams({ month })}`)
}

// Form values -> the body of the Python BudgetInput model. The limit is normalised on the
// string ("200" -> "200.00"); one the form should have rejected is sent as typed, so the
// server's error reaches the user.
export function toBudgetApi({ category, month, limit }) {
  const text = String(limit ?? '').trim()
  return { category, month, limit: parseMoneyInput(text).value ?? text }
}

// Creates the budget for a category and month, or replaces its limit. Resolves the budget.
export function saveBudget(values) {
  return request('/budgets', { method: 'PUT', body: toBudgetApi(values) })
}

export function deleteBudget(month, category) {
  return request(`/budgets/${encodeURIComponent(month)}/${encodeURIComponent(category)}`, { method: 'DELETE' })
}

// Width of the progress bar's fill, 0..100. Display only: the bar stops at the limit, and
// the text next to it carries the real percentage.
export function barPercent(usagePercent) {
  const value = Number(usagePercent)
  if (!Number.isFinite(value)) return 0
  return Math.min(100, Math.max(0, value))
}

// The status in words, so it never depends on the bar's colour. `thresholds` come from the
// API (BUDGET_WARNING and BUDGET_EXCEEDED in Python), not from numbers typed here.
export function statusText(budget, thresholds) {
  if (budget.status === 'exceeded') return `Limit reached: ${thresholds.exceeded}% threshold passed`
  if (budget.status === 'warning') return `Warning: ${thresholds.warning}% threshold passed`
  return `On track: below the ${thresholds.warning}% warning threshold`
}
