import assert from 'node:assert/strict'
import test from 'node:test'
import { FILTER_TRANSACTIONS as rows } from '../src/fixtures/transactions.js'
import { emptyFilters, selectTransactions, sortTransactions } from '../src/lib/transactionFilters.js'

const ids = (items) => items.map((item) => item.id)

test('table defaults to chronological order and preserves equal-date transfers', () => {
  assert.deepEqual(ids(selectTransactions(rows, emptyFilters())), [209, 201, 202, 203, 204, 205, 206, 207, 208, 210])
})

test('descending dates keep equal-date transactions in their input order', () => {
  assert.deepEqual(ids(selectTransactions(rows, {
    ...emptyFilters(), sortDirection: 'desc',
  })), [210, 208, 207, 206, 204, 205, 203, 202, 201, 209])
})

test('amount order compares exact magnitudes numerically and keeps ties stable', () => {
  assert.deepEqual(ids(sortTransactions(rows, 'amount')), [206, 208, 209, 210, 207, 202, 204, 205, 203, 201])
  assert.deepEqual(ids(sortTransactions(rows, 'amount', true)), [201, 203, 204, 205, 202, 207, 210, 208, 209, 206])
})

test('category order is alphabetical and stable in either direction', () => {
  assert.deepEqual(ids(sortTransactions(rows, 'category')), [202, 206, 207, 209, 210, 203, 204, 205, 201, 208])
  assert.deepEqual(ids(sortTransactions(rows, 'category', true)), [208, 201, 204, 205, 203, 202, 206, 207, 209, 210])
})

test('filter, note search and sort state combine into the table result order', () => {
  const settings = {
    ...emptyFilters(), categories: ['Food'], account: '1', note: '  GROCERIES ',
    minimum: '20', sortKey: 'amount', sortDirection: 'desc',
  }
  assert.deepEqual(ids(selectTransactions(rows, settings)), [202, 210, 209])
  assert.equal(settings.note, '  GROCERIES ')
  assert.deepEqual(ids(selectTransactions(rows, {
    ...settings, start: '2026-11-01', end: '2026-11-30',
  })), [202])
})

test('reset restores both default filtering and default sorting', () => {
  const settings = { ...emptyFilters(), kind: 'expense', note: 'lunch', sortKey: 'amount', sortDirection: 'desc' }
  assert.deepEqual(ids(selectTransactions(rows, settings)), [206])
  Object.assign(settings, emptyFilters())
  assert.equal(settings.note, '')
  assert.equal(settings.sortKey, 'date')
  assert.equal(settings.sortDirection, 'asc')
  assert.deepEqual(ids(selectTransactions(rows, settings)), [209, 201, 202, 203, 204, 205, 206, 207, 208, 210])
})

test('sorting preserves the source objects and accepts empty results', () => {
  const original = structuredClone(rows)
  const result = sortTransactions(rows, 'amount')
  assert.deepEqual(rows, original)
  assert.equal(result[0], rows[5])
  assert.deepEqual(selectTransactions(rows, { ...emptyFilters(), note: 'no match' }), [])
  assert.deepEqual(selectTransactions(rows, { ...emptyFilters(), minimum: '30', maximum: '20' }), [])
})

test('invalid sort keys fail even when there are no transactions', () => {
  for (const key of ['note', 'DATE', '__proto__', '']) {
    assert.throws(() => sortTransactions([], key), /choose one of: date, amount, category/)
  }
})

test('filter objects created before sorting was added still work', () => {
  const settings = emptyFilters()
  delete settings.sortKey
  delete settings.sortDirection
  assert.deepEqual(ids(selectTransactions(rows, settings)), [209, 201, 202, 203, 204, 205, 206, 207, 208, 210])
})
