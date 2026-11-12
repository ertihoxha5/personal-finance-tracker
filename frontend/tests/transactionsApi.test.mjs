import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { API_TO_FORM_FIELD, TRANSACTION_TYPES, fromApi, toApi, transactionType } from '../src/api/transactions.js'
import { DEMO_TRANSACTIONS } from '../src/fixtures/transactions.js'

const pythonSource = (path) => readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

test('every kind and direction has a form value, a text label and a sign', () => {
  assert.deepEqual(
    [
      ['income', null],
      ['expense', undefined],
      ['transfer', 'out'],
      ['transfer', 'in'],
    ].map(([kind, direction]) => {
      const { formValue, label, sign } = transactionType(kind, direction)
      return `${formValue}: ${sign} ${label}`
    }),
    ['income: + Income', 'expense: − Expense', 'transfer: − Transfer out', 'transfer: + Transfer in'],
  )
})

test('the lookup covers every Python Kind and Direction', () => {
  const source = pythonSource('pft/domain/category.py')
  const values = (cls) =>
    [...source.split(`class ${cls}(StrEnum):`)[1].split('@classmethod')[0].matchAll(/= "([a-z_]+)"/g)].map((m) => m[1])
  const kinds = new Set(Object.keys(TRANSACTION_TYPES).map((key) => key.split('/')[0]))
  const directions = new Set(Object.keys(TRANSACTION_TYPES).map((key) => key.split('/')[1]).filter(Boolean))
  assert.deepEqual([...kinds].sort(), values('Kind').sort())
  assert.deepEqual([...directions].sort(), values('Direction').sort())
})

test('unknown types get a readable label and message instead of throwing', () => {
  for (const [kind, direction, raw] of [
    ['refund', null, 'refund'],
    ['transfer', null, 'transfer'],
    ['transfer', 'sideways', 'transfer/sideways'],
    ['income', 'in', 'income/in'],
    [undefined, undefined, 'missing'],
  ]) {
    const type = transactionType(kind, direction)
    assert.equal(type.label, 'Unknown type')
    assert.equal(type.sign, '')
    assert.equal(type.raw, raw)
    assert.match(type.error, new RegExp(`"${raw}"`))
  }
  assert.equal(fromApi(null).type.label, 'Unknown type')
})

test('fromApi renames API fields and derives the signed amount on the string', () => {
  const out = fromApi({
    id: 303, account_id: 1, kind: 'transfer', direction: 'out', transfer_id: 'tr-1',
    amount: '300.00', currency: 'EUR', date: '2026-11-05', category: 'other', note: 'Move to savings',
  })
  assert.equal(out.accountId, 1)
  assert.equal(out.transferId, 'tr-1')
  assert.equal(out.type.label, 'Transfer out')
  assert.equal(out.signedAmount, '-300.00')
  assert.equal(fromApi({ kind: 'expense', amount: '0.10', direction: '' }).signedAmount, '-0.10')
  assert.equal(fromApi({ kind: 'income', amount: '2200.00' }).signedAmount, '2200.00')
  assert.equal(fromApi({ kind: 'refund', amount: '9.99' }).signedAmount, '9.99')
})

test('the demo rows add up like the Python signed_amount, ignoring the unknown kind', () => {
  const rows = DEMO_TRANSACTIONS.map(fromApi).filter((row) => !row.type.error)
  const cents = rows.map((row) => BigInt(row.signedAmount.replace('.', '')))
  assert.equal(cents.reduce((a, b) => a + b, 0n), 212300n) // 2200 − 64.50 − 12.50
})

test('the demo fixture covers every known type and one unknown one', () => {
  const labels = new Set(DEMO_TRANSACTIONS.map((dto) => fromApi(dto).type.label))
  for (const type of Object.values(TRANSACTION_TYPES)) assert.ok(labels.has(type.label), type.label)
  assert.ok(labels.has('Unknown type'))
})

test('toApi builds the API body with a normalised amount, integer account id and trimmed note', () => {
  assert.deepEqual(
    toApi({ kind: 'expense', accountId: '3', amount: '12,5', date: '2026-11-15', category: 'food', note: '  Lunch ' }),
    { kind: 'expense', account_id: 3, amount: '12.50', date: '2026-11-15', category: 'food', note: 'Lunch' },
  )
  assert.equal(toApi({ kind: 'expense', accountId: '1', amount: 'abc' }).amount, 'abc')
})

test('API field names and DTO keys match the Python CSV columns', () => {
  const source = pythonSource('pft/domain/transaction.py')
  const columns = [...source.split('CSV_COLUMNS: tuple[str, ...] = (')[1].split(')')[0].matchAll(/"([a-z_]+)"/g)].map(
    (m) => m[1],
  )
  const dto = toApi({ kind: 'income', accountId: '1', amount: '1.00', date: '2026-11-15', category: 'salary', note: '' })
  for (const key of [...Object.keys(dto), ...Object.keys(API_TO_FORM_FIELD)]) assert.ok(columns.includes(key), key)
})
