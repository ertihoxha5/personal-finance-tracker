import { request } from './http.js'
import { categoryLabel } from '../lib/labels.js'

// Dashboard client (#19): GET /api/dashboard?month=YYYY-MM, built by pft.services.reports
// (MonthlySummary). Totals, savings rate, category totals and the previous-month change are
// all calculated by the server; this file only renames fields and attaches display labels.
// Leave the month out to get the latest month that has data.

const toCategory = (dto) => ({
  id: dto.category,
  name: categoryLabel(dto.category),
  total: dto.total,
})

// The API sends an unsigned amount and a kind; the lists show expenses as negative.
// This is a string operation, never Number(), so no rounding creeps in.
const signed = (dto) => (dto.kind === 'expense' ? `-${dto.amount}` : dto.amount)

const toTransaction = (dto) => ({
  id: dto.id,
  date: dto.date,
  description: dto.note || categoryLabel(dto.category),
  category: { id: dto.category, name: categoryLabel(dto.category) },
  account: dto.account,
  amount: signed(dto),
})

const toTotals = (dto) => ({
  income: dto.income,
  expenses: dto.expenses,
  net: dto.net,
  savingsRate: dto.savings_rate,
  transactionCount: dto.transaction_count,
})

export async function fetchDashboard(month) {
  const query = month ? `?month=${encodeURIComponent(month)}` : ''
  const dto = await request(`/dashboard${query}`)
  return {
    month: dto.month,
    currency: dto.currency,
    availableMonths: dto.available_months,
    summary: toTotals(dto.summary),
    // The previous month, with its change; `hasData` tells the card whether to compare.
    previous: {
      ...toTotals(dto.previous),
      month: dto.previous.month,
      hasData: dto.previous.transaction_count > 0,
      changes: dto.changes,
    },
    topCategories: dto.top_categories.map(toCategory),
    categories: dto.categories.map(toCategory),
    trend: dto.trend,
    recentTransactions: dto.recent_transactions.map(toTransaction),
  }
}
