import assert from 'node:assert/strict'
import test from 'node:test'
import { FILTER_TRANSACTIONS as rows } from '../src/fixtures/transactions.js'
import { emptyFilters, filterTransactions, validateFilters } from '../src/lib/transactionFilters.js'

test('reset defaults preserve all rows in their original order', () => {
  assert.deepEqual(filterTransactions(rows, emptyFilters()), rows)
})

test('all filter groups combine, while categories allow multiple choices', () => {
  const filters = {
    ...emptyFilters(), categories: ['Food', 'Transport'], kind: 'expense', account: '1',
    start: '2026-11-01', end: '2026-11-30', minimum: '20.01', maximum: '100', note: 'GROCERIES',
  }
  assert.deepEqual(filterTransactions(rows, filters).map((row) => row.id), [202])
  assert.deepEqual(filterTransactions(rows, {
    ...emptyFilters(), categories: ['Housing', 'Transport'],
  }).map((row) => row.id), [203, 208])
})

test('date and decimal amount bounds are inclusive', () => {
  assert.deepEqual(filterTransactions(rows, {
    ...emptyFilters(), start: '2026-11-30', end: '2026-12-01',
  }).map((row) => row.id), [208, 210])
  assert.deepEqual(filterTransactions(rows, {
    ...emptyFilters(), minimum: '20,01', maximum: '20.01',
  }).map((row) => row.id), [210])
})

test('invalid bounds produce errors and suppress results until corrected', () => {
  for (const patch of [
    { minimum: '30', maximum: '20' },
    { minimum: 'abc' },
    { maximum: '12.345' },
    { start: '2026-12-01', end: '2026-11-01' },
  ]) {
    const filters = { ...emptyFilters(), ...patch }
    assert.ok(Object.keys(validateFilters(filters).errors).length)
    assert.deepEqual(filterTransactions(rows, filters), [])
  }
})

test('note search trims whitespace, ignores case and supports empty results', () => {
  assert.deepEqual(filterTransactions(rows, {
    ...emptyFilters(), note: '  STUDY GROUP  ',
  }).map((row) => row.id), [207])
  assert.deepEqual(filterTransactions(rows, { ...emptyFilters(), note: 'unmatched note' }), [])
})

test('transfer filtering preserves both directions and never mutates source data', () => {
  const original = structuredClone(rows)
  assert.deepEqual(filterTransactions(rows, {
    ...emptyFilters(), kind: 'transfer', minimum: '300', maximum: '300',
  }).map((row) => [row.id, row.direction]), [[204, 'out'], [205, 'in']])
  assert.deepEqual(rows, original)
})
