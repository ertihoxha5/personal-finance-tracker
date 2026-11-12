import assert from 'node:assert/strict'
import test from 'node:test'
import { filenameError, reportExport, requestCsv, transactionExport } from '../src/api/exports.js'
import { FILTER_TRANSACTIONS } from '../src/fixtures/transactions.js'
import { DASHBOARD_FIXTURES } from '../src/fixtures/dashboard.js'
import { emptyFilters, selectTransactions } from '../src/lib/transactionFilters.js'

test('transaction download captures filtered and sorted rows with selection metadata', () => {
  const filters = { ...emptyFilters(), note: 'groceries', sortKey: 'amount', sortDirection: 'desc' }
  const payload = transactionExport(selectTransactions(FILTER_TRANSACTIONS, filters), filters)
  assert.deepEqual(payload.rows.map((row) => row.id), ['202', '210', '209'])
  assert.deepEqual(payload.filters, filters)
  filters.note = ''
  assert.equal(payload.filters.note, 'groceries')
  assert.deepEqual(Object.keys(payload.rows[0]), payload.columns)
  assert.equal(payload.rows[0].amount, '64.50')
  assert.equal(payload.rows[0].currency, 'EUR')
})

test('empty transaction selection still supplies the CSV schema', () => {
  const payload = transactionExport([], emptyFilters())
  assert.equal(payload.columns.length, 10)
  assert.deepEqual(payload.rows, [])
})

test('report download uses the selected month and existing summary/category values', () => {
  const data = DASHBOARD_FIXTURES['2026-11']
  const payload = reportExport(data)
  assert.deepEqual(payload.filters, { month: '2026-11' })
  assert.ok(payload.rows.every((row) => row.month === '2026-11'))
  assert.equal(payload.rows.find((row) => row.label === 'income').value, data.summary.income)
  assert.equal(payload.rows.find((row) => row.label === 'savingsRate').unit, '%')
  assert.equal(payload.rows.filter((row) => row.section === 'category').length, data.categories.length)
  assert.deepEqual(Object.keys(payload.rows[0]), payload.columns)
})

test('filename validation accepts CSV names and rejects paths and header injection', () => {
  assert.equal(filenameError('monthly-report-2026-11.csv'), null)
  for (const filename of ['', '../report.csv', 'report.txt', 'a.csv\r\nX-Test: bad', 'a'.repeat(101) + '.csv']) {
    assert.ok(filenameError(filename))
  }
})

test('download request sends filename, filters and rows and returns the CSV blob', async () => {
  const payload = { ...transactionExport([], emptyFilters()), filename: 'transactions.csv' }
  const controller = new AbortController()
  let calls = 0
  const blob = await requestCsv(payload, {
    signal: controller.signal,
    fetchImpl: async (url, options) => {
      calls += 1
      assert.equal(url, '/api/exports/csv')
      assert.equal(options.method, 'POST')
      assert.equal(options.signal, controller.signal)
      assert.deepEqual(JSON.parse(options.body), payload)
      return new Response('id,note\r\n', { headers: { 'Content-Type': 'text/csv; charset=utf-8' } })
    },
  })
  assert.equal(calls, 1)
  assert.equal(await blob.text(), 'id,note\r\n')
})

test('failed responses report a usable error and can be retried', async () => {
  const payload = { filename: 'transactions.csv', rows: [], columns: ['id'], filters: {} }
  let calls = 0
  const fetchImpl = async () => {
    calls += 1
    if (calls === 1) return new Response(JSON.stringify({ detail: 'Please try again.' }), { status: 500 })
    return new Response('id\r\n', { headers: { 'Content-Type': 'text/csv' } })
  }
  await assert.rejects(requestCsv(payload, { fetchImpl }), /Please try again/)
  assert.equal(await (await requestCsv(payload, { fetchImpl })).text(), 'id\r\n')
})

test('unexpected server responses and network failures are rejected', async () => {
  const payload = { filename: 'report.csv' }
  await assert.rejects(requestCsv(payload, {
    fetchImpl: async () => new Response('<html>Vite fallback</html>', { headers: { 'Content-Type': 'text/html' } }),
  }), /unexpected response/)
  await assert.rejects(requestCsv(payload, {
    fetchImpl: async () => { throw new TypeError('Failed to fetch') },
  }), /Failed to fetch/)
  await assert.rejects(requestCsv({ filename: '../report.csv' }), /filename/)
})

test('an older running backend gives an actionable endpoint error', async () => {
  await assert.rejects(requestCsv({ filename: 'report.csv' }, {
    fetchImpl: async () => new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 }),
  }), /Restart the backend/)
})
