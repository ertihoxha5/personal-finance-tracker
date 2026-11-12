import assert from 'node:assert/strict'
import test from 'node:test'
import { createTransaction, searchTransactions, transactionQuery } from '../src/api/transactions.js'
import { emptyFilters } from '../src/lib/transactionFilters.js'

function mockFetch(body, status = 200) {
  const calls = []
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, ...options })
    return { ok: status < 400, status, json: async () => body }
  }
  return calls
}

test('no filters still sends the default sort', () => {
  assert.equal(transactionQuery(emptyFilters()), 'sort=date&direction=asc')
})

test('every filter becomes the matching query parameter', () => {
  const query = new URLSearchParams(
    transactionQuery({
      ...emptyFilters(),
      categories: ['food', 'rent'],
      kind: 'expense',
      account: '2',
      start: '2026-11-01',
      end: '2026-11-30',
      minimum: '5,5',
      maximum: '100',
      note: '  lunch ',
      sortKey: 'amount',
      sortDirection: 'desc',
    }),
  )
  assert.deepEqual(query.getAll('category'), ['food', 'rent'])
  assert.equal(query.get('account_id'), '2')
  assert.equal(query.get('kind'), 'expense')
  assert.equal(query.get('start'), '2026-11-01')
  assert.equal(query.get('end'), '2026-11-30')
  assert.equal(query.get('min_amount'), '5.50') // the decimal comma is normalised
  assert.equal(query.get('max_amount'), '100.00')
  assert.equal(query.get('q'), 'lunch')
  assert.equal(query.get('sort'), 'amount')
  assert.equal(query.get('direction'), 'desc')
})

test('searching asks the server and returns its rows untouched', async () => {
  const rows = [{ id: 1, account_id: 1, kind: 'expense', amount: '12.50', note: 'Lunch' }]
  const calls = mockFetch(rows)
  assert.deepEqual(await searchTransactions({ ...emptyFilters(), kind: 'expense' }), rows)
  assert.equal(calls[0].url, '/api/transactions?kind=expense&sort=date&direction=asc')
})

test('creating posts the form body as JSON and surfaces a server error with its field', async () => {
  const calls = mockFetch({ id: 4 }, 201)
  const body = { kind: 'expense', account_id: 1, amount: '4.50', date: '2026-11-10', category: 'food', note: '' }
  await createTransaction(body)
  assert.equal(calls[0].method, 'POST')
  assert.deepEqual(JSON.parse(calls[0].body), body)

  mockFetch({ code: 'invalid_amount', message: 'invalid amount', field: 'amount' }, 422)
  await assert.rejects(createTransaction(body), (error) => error.status === 422 && error.field === 'amount')
})
