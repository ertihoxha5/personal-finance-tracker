import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { DEMO_TRANSACTIONS } from '../src/fixtures/transactions.js'
import { isoDate, kindDisplay, signedAmount, toDto, todayISO } from '../src/lib/transactions.js'

test('every kind has a text label and a sign, not just a tone', () => {
  assert.deepEqual(
    [
      { kind: 'income' },
      { kind: 'expense' },
      { kind: 'transfer', direction: 'out' },
      { kind: 'transfer', direction: 'in' },
    ].map((tx) => {
      const { label, sign } = kindDisplay(tx)
      return `${sign} ${label}`
    }),
    ['+ Income', '− Expense', '− Transfer out', '+ Transfer in'],
  )
})

test('unknown kinds and transfers without a direction still get a label', () => {
  assert.equal(kindDisplay({ kind: 'refund' }).label, 'Unknown')
  assert.equal(kindDisplay(null).label, 'Unknown')
  assert.deepEqual(kindDisplay({ kind: 'transfer' }), { label: 'Transfer', sign: '', tone: 'transfer' })
})

test('signedAmount applies the sign on the string', () => {
  assert.equal(signedAmount({ kind: 'income', amount: '2200.00' }), '2200.00')
  assert.equal(signedAmount({ kind: 'expense', amount: '0.10' }), '-0.10')
  assert.equal(signedAmount({ kind: 'transfer', direction: 'out', amount: '300.00' }), '-300.00')
  assert.equal(signedAmount({ kind: 'transfer', direction: 'in', amount: '300.00' }), '300.00')
})

test('the demo rows add up like the Python signed_amount', () => {
  const cents = DEMO_TRANSACTIONS.map((tx) => BigInt(signedAmount(tx).replace('.', '')))
  assert.equal(cents.reduce((a, b) => a + b, 0n), 212300n) // 2200 − 64.50 − 12.50
})

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

test('toDto builds the API body with an integer account id and a trimmed note', () => {
  assert.deepEqual(
    toDto({ kind: 'expense', accountId: '3', amount: '12.50', date: '2026-11-15', category: 'food', note: '  Lunch ' }),
    { kind: 'expense', account_id: 3, amount: '12.50', date: '2026-11-15', category: 'food', note: 'Lunch' },
  )
})

test('dto keys match the Python CSV columns they map to', () => {
  const source = readFileSync(new URL('../../pft/domain/transaction.py', import.meta.url), 'utf8')
  const columns = [...source.split('CSV_COLUMNS: tuple[str, ...] = (')[1].split(')')[0].matchAll(/"([a-z_]+)"/g)].map(
    (m) => m[1],
  )
  const dto = toDto({ kind: 'income', accountId: '1', amount: '1.00', date: '2026-11-15', category: 'salary', note: '' })
  for (const key of Object.keys(dto)) assert.ok(columns.includes(key), key)
})
