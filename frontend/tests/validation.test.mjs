import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { AMOUNT_REQUIRED_MESSAGE, POSITIVE_MESSAGE, REQUIRED_MESSAGE, positiveDecimal, required, validateFields } from '../src/lib/validation.js'

test('required rejects missing, empty and whitespace-only values', () => {
  for (const value of [null, undefined, '', '   ', '\t\n']) {
    assert.equal(required(value), REQUIRED_MESSAGE, JSON.stringify(value))
  }
  assert.equal(required('Rent'), null)
  assert.equal(required('', 'Choose a category.'), 'Choose a category.')
})

test('positiveDecimal accepts positive decimal strings', () => {
  for (const text of ['12', '12.50', '12,5', '.5', '0.01', '007', ' 3 ']) {
    assert.equal(positiveDecimal(text), null, text)
  }
})

test('positiveDecimal rejects zero in every spelling', () => {
  for (const text of ['0', '0.00', '0,0', '.0', '000', '-0']) {
    assert.notEqual(positiveDecimal(text), null, text)
  }
  assert.equal(positiveDecimal('0.00'), POSITIVE_MESSAGE)
})

test('positiveDecimal rejects negatives, junk and too many decimals', () => {
  assert.equal(positiveDecimal('-5'), 'Enter an amount like 12.50.')
  assert.equal(positiveDecimal('abc'), 'Enter an amount like 12.50.')
  assert.equal(positiveDecimal('1,250.00'), 'Enter an amount like 12.50.')
  assert.equal(positiveDecimal('1.234'), 'Use at most 2 decimal places.')
  assert.equal(positiveDecimal(''), AMOUNT_REQUIRED_MESSAGE)
  assert.equal(positiveDecimal(12), AMOUNT_REQUIRED_MESSAGE)
})

test('validateFields returns the first failing message per field, in rule order', () => {
  const rules = {
    description: required,
    amount: [required, positiveDecimal],
    category: (value) => required(value, 'Choose a category.'),
  }
  const errors = validateFields({ description: ' ', amount: '0', category: '' }, rules)
  assert.deepEqual(errors, {
    description: REQUIRED_MESSAGE,
    amount: POSITIVE_MESSAGE,
    category: 'Choose a category.',
  })
  assert.deepEqual(Object.keys(errors), ['description', 'amount', 'category'])
  assert.deepEqual(validateFields({ description: 'Rent', amount: '850', category: 'rent' }, rules), {})
})

test('amounts are never converted to numbers', () => {
  const source = readFileSync(new URL('../src/lib/validation.js', import.meta.url), 'utf8')
  const code = source.replace(/\/\/.*$/gm, '')
  assert.doesNotMatch(code, /parseFloat|Number\(|parseInt/)
})
