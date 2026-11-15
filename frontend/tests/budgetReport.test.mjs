import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { fetchBudgetReport, splitDifference } from '../src/api/budgetReport.js'
import { BUDGET_STATUS_LABELS, budgetStatusLabel } from '../src/lib/labels.js'

function mockFetch(status, body) {
  const calls = []
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, ...options })
    return { ok: status < 400, status, json: async () => body }
  }
  return calls
}

const dto = {
  month: '2026-11',
  currency: 'EUR',
  rows: [
    { category: 'food', planned: '200.00', actual: '165.00', difference: '35.00', usage_percent: '82.5', status: 'warning' },
    { category: 'rent', planned: '600.00', actual: '610.00', difference: '-10.00', usage_percent: '101.6', status: 'over' },
  ],
  totals: { planned: '800.00', actual: '775.00', difference: '25.00' },
}

test('the month filter goes to the server as ?month=YYYY-MM', async () => {
  const calls = mockFetch(200, dto)
  await fetchBudgetReport('2026-11')
  assert.equal(calls[0].url, '/api/reports/budget?month=2026-11')
})

test('rows keep the server amounts as strings and gain labels', async () => {
  mockFetch(200, dto)
  const report = await fetchBudgetReport('2026-11')
  assert.deepEqual(report.rows[0], {
    id: 'food', name: 'Food', planned: '200.00', actual: '165.00',
    difference: { over: false, amount: '35.00' }, usagePercent: '82.5',
    status: 'warning', statusLabel: 'Warning',
  })
  assert.deepEqual(report.rows[1].difference, { over: true, amount: '10.00' })
  assert.equal(report.rows[1].statusLabel, 'Over')
  assert.deepEqual(report.totals, {
    planned: '800.00', actual: '775.00', difference: { over: false, amount: '25.00' },
  })
})

test('a month without budgets maps to an empty list, not an error', async () => {
  mockFetch(200, { month: '2026-12', currency: 'EUR', rows: [], totals: { planned: '0.00', actual: '0.00', difference: '0.00' } })
  const report = await fetchBudgetReport('2026-12')
  assert.deepEqual(report.rows, [])
  assert.deepEqual(report.totals.difference, { over: false, amount: '0.00' })
})

test('a bad month rejects with the server message and field', async () => {
  mockFetch(422, { code: 'invalid_date', message: "invalid month '11/2026'; use the form 2026-11", field: 'month' })
  await assert.rejects(fetchBudgetReport('11/2026'), (error) => {
    assert.equal(error.field, 'month')
    assert.equal(error.code, 'invalid_date')
    return true
  })
})

test('splitDifference works on the string, without rounding', () => {
  assert.deepEqual(splitDifference('-0.10'), { over: true, amount: '0.10' })
  assert.deepEqual(splitDifference('12345678.90'), { over: false, amount: '12345678.90' })
})

test('status labels are keyed by exactly the Python BudgetStatus values', () => {
  const source = readFileSync(new URL('../../pft/services/reports.py', import.meta.url), 'utf8')
  const body = source.slice(source.indexOf('class BudgetStatus'), source.indexOf('class BudgetLine'))
  const values = [...body.matchAll(/^ {4}[A-Z]+ = "(\w+)"/gm)].map((m) => m[1])
  assert.deepEqual(Object.keys(BUDGET_STATUS_LABELS).sort(), values.sort())
  assert.equal(budgetStatusLabel('paused'), 'Paused') // an unknown value still reads sensibly
})
