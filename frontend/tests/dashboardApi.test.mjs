import assert from 'node:assert/strict'
import test from 'node:test'
import { fetchDashboard } from '../src/api/dashboard.js'
import { reportExport } from '../src/api/exports.js'

const RESPONSE = {
  month: '2026-11',
  currency: 'EUR',
  available_months: ['2026-10', '2026-11'],
  summary: { income: '800.00', expenses: '600.00', net: '200.00', savings_rate: '25.0', transaction_count: 3 },
  previous: { month: '2026-10', income: '500.00', expenses: '300.00', net: '200.00', savings_rate: '40.0', transaction_count: 2 },
  changes: { income: '300.00', expenses: '300.00', net: '0.00' },
  top_categories: [{ category: 'rent', total: '500.00' }],
  categories: [{ category: 'rent', total: '500.00' }, { category: 'food', total: '100.00' }],
  trend: [{ month: '2026-11', income: '800.00', expenses: '600.00' }],
  recent_transactions: [
    { id: 2, date: '2026-11-03', note: 'Rent', category: 'rent', kind: 'expense', account: { id: 1, name: 'Bank' }, amount: '500.00' },
    { id: 1, date: '2026-11-01', note: '', category: 'salary', kind: 'income', account: { id: 1, name: 'Bank' }, amount: '800.00' },
  ],
}

function mockFetch(body, status = 200) {
  const calls = []
  globalThis.fetch = async (url) => {
    calls.push(url)
    return { ok: status < 400, status, json: async () => body }
  }
  return calls
}

test('the month is sent as a query, and left out to let the server choose', async () => {
  const calls = mockFetch(RESPONSE)
  await fetchDashboard('2026-11')
  await fetchDashboard(null)
  assert.deepEqual(calls, ['/api/dashboard?month=2026-11', '/api/dashboard'])
})

test('server numbers pass through as strings, with labels and signs added for display', async () => {
  mockFetch(RESPONSE)
  const data = await fetchDashboard('2026-11')
  assert.deepEqual(data.summary, {
    income: '800.00', expenses: '600.00', net: '200.00', savingsRate: '25.0', transactionCount: 3,
  })
  assert.equal(data.previous.hasData, true)
  assert.deepEqual(data.previous.changes, RESPONSE.changes)
  assert.deepEqual(data.topCategories, [{ id: 'rent', name: 'Rent', total: '500.00' }])
  assert.deepEqual(data.recentTransactions.map((t) => [t.description, t.amount]), [
    ['Rent', '-500.00'],
    ['Salary', '800.00'], // no note: the category label is shown
  ])
})

test('a previous month without transactions is flagged so the card does not compare', async () => {
  mockFetch({ ...RESPONSE, previous: { ...RESPONSE.previous, transaction_count: 0 } })
  assert.equal((await fetchDashboard('2026-11')).previous.hasData, false)
})

test('a server error rejects with its message and status', async () => {
  mockFetch({ code: 'invalid_date', message: 'invalid month', field: 'month' }, 422)
  await assert.rejects(fetchDashboard('nope'), (error) => error.status === 422 && error.field === 'month')
})

test('the report CSV exports the money figures only, not the transaction count', async () => {
  mockFetch(RESPONSE)
  const rows = reportExport(await fetchDashboard('2026-11')).rows
  assert.deepEqual(rows.filter((r) => r.section === 'summary').map((r) => r.label), [
    'income', 'expenses', 'net', 'savingsRate',
  ])
})
