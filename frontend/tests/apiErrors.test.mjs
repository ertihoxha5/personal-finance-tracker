import assert from 'node:assert/strict'
import test from 'node:test'
import { ApiError } from '../src/api/accounts.js'
import {
  CATEGORY_ERROR,
  FIELD_ERROR,
  MULTIPLE_ERRORS,
  PAGE_ERROR,
  SERVER_ERROR,
} from '../src/fixtures/apiErrors.js'
import { NETWORK_MESSAGE, SERVER_MESSAGE, UNKNOWN_MESSAGE, mapApiError } from '../src/lib/apiErrors.js'

test('an error with a field goes inline, with a readable message', () => {
  assert.deepEqual(mapApiError(FIELD_ERROR), {
    fieldErrors: { amount: 'Enter an amount greater than zero' },
    pageAlert: null,
  })
})

test('an error without a field goes to a page alert that is not retried', () => {
  assert.deepEqual(mapApiError(PAGE_ERROR), {
    fieldErrors: {},
    pageAlert: {
      code: 'account_not_found',
      message: 'That account no longer exists; refresh the list',
      retryable: false,
    },
  })
})

test('a list of errors is split between fields and one page alert', () => {
  const { fieldErrors, pageAlert } = mapApiError(MULTIPLE_ERRORS)
  assert.deepEqual(Object.keys(fieldErrors), ['amount', 'category'])
  assert.match(fieldErrors.category, /^Unknown category 'groceries'; choose one of: salary,/)
  assert.equal(pageAlert.code, 'account_not_found')
  assert.deepEqual(mapApiError([FIELD_ERROR, CATEGORY_ERROR]).pageAlert, null)
})

test('the first message for a field wins', () => {
  const second = { ...FIELD_ERROR, message: 'second' }
  assert.equal(mapApiError([FIELD_ERROR, second]).fieldErrors.amount, 'Enter an amount greater than zero')
})

test('network failures and server errors are retryable page alerts', () => {
  assert.deepEqual(mapApiError(new TypeError('Failed to fetch')).pageAlert, {
    code: 'network_error',
    message: NETWORK_MESSAGE,
    retryable: true,
  })
  assert.deepEqual(mapApiError(SERVER_ERROR).pageAlert, {
    code: 'server_error',
    message: SERVER_MESSAGE,
    retryable: true,
  })
})

test('ApiError from the stand-in API maps the same way', () => {
  const inline = mapApiError(new ApiError('Enter a name for the account.', { field: 'name' }))
  assert.deepEqual(inline.fieldErrors, { name: 'Enter a name for the account.' })
  const page = mapApiError(new ApiError('The server could not save that change.', { status: 500 }))
  assert.equal(page.pageAlert.retryable, true)
  assert.equal(page.pageAlert.message, 'The server could not save that change.')
})

test('unexpected values never throw and produce a generic retryable alert', () => {
  for (const value of ['oops', 42, {}, { field: 'amount' }, [null]]) {
    const { pageAlert } = mapApiError(value)
    assert.equal(pageAlert.message, UNKNOWN_MESSAGE)
    assert.equal(pageAlert.retryable, true)
  }
  assert.deepEqual(mapApiError(undefined), { fieldErrors: {}, pageAlert: null })
})
