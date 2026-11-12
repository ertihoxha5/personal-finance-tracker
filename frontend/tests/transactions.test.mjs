import assert from 'node:assert/strict'
import test from 'node:test'
import { isoDate, todayISO } from '../src/lib/transactions.js'

// DTO mapping (labels, signs, field names) moved to api/transactions.js in #17;
// see transactionsApi.test.mjs.

test('todayISO uses the local date', () => {
  assert.equal(todayISO(new Date(2026, 10, 5, 23, 59)), '2026-11-05')
  assert.equal(todayISO(new Date(2026, 0, 1, 0, 1)), '2026-01-01')
})

test('isoDate accepts real dates only', () => {
  assert.equal(isoDate('2026-11-15'), null)
  assert.equal(isoDate('2028-02-29'), null)
  assert.equal(isoDate(''), 'Enter a date.')
  assert.equal(isoDate('15/11/2026'), 'Enter a date like 2026-11-15.')
  assert.equal(isoDate('2026-02-30'), 'That date does not exist.')
  assert.equal(isoDate('2026-13-01'), 'That date does not exist.')
})
