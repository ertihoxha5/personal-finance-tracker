import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { barPercent, deleteBudget, listBudgets, saveBudget, statusText, toBudgetApi } from '../src/api/budgets.js'

function mockFetch(status, body) {
  const calls = []
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, ...options })
    return { ok: status < 400, status, json: async () => body }
  }
  return calls
}

const thresholds = { warning: 80, exceeded: 100 }

test('toBudgetApi normalises the limit as a string', () => {
  assert.deepEqual(toBudgetApi({ category: 'food', month: '2026-11', limit: ' 200 ' }), {
    category: 'food', month: '2026-11', limit: '200.00',
  })
  assert.equal(toBudgetApi({ category: 'food', month: '2026-11', limit: '12,5' }).limit, '12.50')
  // Something the form should have rejected goes to the server as typed.
  assert.equal(toBudgetApi({ category: 'food', month: '2026-11', limit: 'abc' }).limit, 'abc')
})

test('the request body uses exactly the fields of the Python BudgetInput model', () => {
  const source = readFileSync(new URL('../../pft/api/budgets.py', import.meta.url), 'utf8')
  const model = source.slice(source.indexOf('class BudgetInput'), source.indexOf('def _limit'))
  const fields = [...model.matchAll(/^ {4}(\w+):/gm)].map((m) => m[1])
  assert.deepEqual(Object.keys(toBudgetApi({ category: 'food', month: '2026-11', limit: '1' })).sort(), fields.sort())
})

test('requests go to the budget routes', async () => {
  const calls = mockFetch(200, {})
  await listBudgets('2026-11')
  await saveBudget({ category: 'food', month: '2026-11', limit: '200' })
  await deleteBudget('2026-11', 'food')
  assert.deepEqual(calls.map((c) => [c.method, c.url]), [
    ['GET', '/api/budgets?month=2026-11'],
    ['PUT', '/api/budgets'],
    ['DELETE', '/api/budgets/2026-11/food'],
  ])
  assert.deepEqual(JSON.parse(calls[1].body), { category: 'food', month: '2026-11', limit: '200.00' })
})

test('a server error keeps its field so the form can show it under the input', async () => {
  mockFetch(422, { code: 'budget_error', message: 'a budget limit must be more than zero', field: 'limit' })
  await assert.rejects(saveBudget({ category: 'food', month: '2026-11', limit: '0' }), (error) => {
    assert.equal(error.field, 'limit')
    assert.equal(error.code, 'budget_error')
    return true
  })
})

test('statusText names the threshold in words, using the numbers from the API', () => {
  assert.equal(statusText({ status: 'ok' }, thresholds), 'On track: below the 80% warning threshold')
  assert.equal(statusText({ status: 'warning' }, thresholds), 'Warning: 80% threshold passed')
  assert.equal(statusText({ status: 'exceeded' }, thresholds), 'Limit reached: 100% threshold passed')
  assert.match(statusText({ status: 'warning' }, { warning: 75, exceeded: 100 }), /75%/)
})

test('barPercent keeps the bar between 0 and 100', () => {
  assert.equal(barPercent('82.5'), 82.5)
  assert.equal(barPercent('105.0'), 100)
  assert.equal(barPercent('0.0'), 0)
  assert.equal(barPercent(undefined), 0)
})
