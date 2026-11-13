import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import {
  RECURRING_FIELD_TO_FORM,
  createRecurring,
  previewRecurring,
  recurringPreviewQuery,
  toRecurringApi,
} from '../src/api/recurring.js'

function mockFetch(status, body) {
  const calls = []
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, ...options })
    return { ok: status < 400, status, json: async () => body }
  }
  return calls
}

const form = {
  kind: 'expense', accountId: '1', amount: '600', date: '2027-01-31', category: 'rent',
  note: ' Flat rent ', frequency: 'monthly', endDate: '',
}

test('toRecurringApi sends the date as start_date and an empty end as null', () => {
  assert.deepEqual(toRecurringApi(form), {
    kind: 'expense', account_id: 1, amount: '600.00', category: 'rent', note: 'Flat rent',
    frequency: 'monthly', start_date: '2027-01-31', end_date: null,
  })
  assert.equal(toRecurringApi({ ...form, endDate: '2027-06-30' }).end_date, '2027-06-30')
})

test('the request body uses exactly the fields of the Python NewRecurring model', () => {
  const source = readFileSync(new URL('../../pft/api/recurring.py', import.meta.url), 'utf8')
  const model = source.slice(source.indexOf('class NewRecurring'), source.indexOf('def _end'))
  const fields = [...model.matchAll(/^ {4}(\w+):/gm)].map((m) => m[1])
  assert.deepEqual(Object.keys(toRecurringApi(form)).sort(), fields.sort())
  for (const apiField of Object.keys(RECURRING_FIELD_TO_FORM)) assert.ok(fields.includes(apiField), apiField)
})

test('preview query names the frequency, start, optional end and count', () => {
  assert.equal(
    recurringPreviewQuery({ frequency: 'monthly', startDate: '2027-01-31' }),
    'frequency=monthly&start_date=2027-01-31&count=6',
  )
  assert.equal(
    recurringPreviewQuery({ frequency: 'weekly', startDate: '2027-01-01', endDate: '2027-02-01', count: 3 }),
    'frequency=weekly&start_date=2027-01-01&count=3&end_date=2027-02-01',
  )
})

test('preview and create call the recurring routes', async () => {
  const preview = { due_count: 0, due_now: [], upcoming: ['2027-02-28', '2027-03-31'] }
  let calls = mockFetch(200, preview)
  assert.deepEqual(await previewRecurring({ frequency: 'monthly', startDate: '2027-01-31' }), preview)
  assert.equal(calls[0].url, '/api/recurring/preview?frequency=monthly&start_date=2027-01-31&count=6')

  calls = mockFetch(201, { rule: {}, added: [] })
  await createRecurring(toRecurringApi(form))
  assert.equal(calls[0].url, '/api/recurring')
  assert.equal(calls[0].method, 'POST')
  assert.equal(JSON.parse(calls[0].body).start_date, '2027-01-31')
})

test('a server error on end_date reaches the form as endDate', async () => {
  mockFetch(422, { code: 'invalid_date', message: 'end date must be on or after the start date', field: 'end_date' })
  await assert.rejects(createRecurring(toRecurringApi(form)), (error) => {
    assert.equal(RECURRING_FIELD_TO_FORM[error.field], 'endDate')
    return true
  })
})
