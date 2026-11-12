import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import {
  ACCOUNT_TYPE_LABELS,
  CATEGORY_LABELS,
  FREQUENCY_LABELS,
  KIND_LABELS,
  accountTypeLabel,
  categoryLabel,
  fallbackLabel,
  toOptions,
} from '../src/lib/labels.js'

// Read the Python enums so the label keys can never drift from the API values.
const pythonSource = readFileSync(new URL('../../pft/domain/category.py', import.meta.url), 'utf8')

function pythonEnumValues(name) {
  const body = pythonSource.split(new RegExp(`class ${name}\\(StrEnum\\):`))[1].split(/\nclass |\ndef /)[0]
  return [...body.matchAll(/^ {4}[A-Z_]+ = "([a-z_]+)"$/gm)].map((match) => match[1])
}

for (const [name, labels] of [
  ['Category', CATEGORY_LABELS],
  ['Kind', KIND_LABELS],
  ['AccountType', ACCOUNT_TYPE_LABELS],
  ['Frequency', FREQUENCY_LABELS],
]) {
  test(`${name} label keys match the Python enum values in order`, () => {
    const values = pythonEnumValues(name)
    assert.ok(values.length > 0)
    assert.deepEqual(Object.keys(labels), values)
  })
}

test('known values get their readable label', () => {
  assert.equal(categoryLabel('food'), 'Food')
  assert.equal(accountTypeLabel('savings'), 'Savings')
})

test('unknown values fall back to a readable form instead of breaking', () => {
  assert.equal(categoryLabel('credit_line'), 'Credit line')
  assert.equal(categoryLabel('GIFTS'), 'Gifts')
  assert.equal(fallbackLabel(''), 'Unknown')
  assert.equal(fallbackLabel(null), 'Unknown')
  assert.equal(categoryLabel('toString'), 'Tostring')
})

test('toOptions keeps API order for selects', () => {
  assert.deepEqual(toOptions(KIND_LABELS), [
    { value: 'income', label: 'Income' },
    { value: 'expense', label: 'Expense' },
    { value: 'transfer', label: 'Transfer' },
  ])
})
