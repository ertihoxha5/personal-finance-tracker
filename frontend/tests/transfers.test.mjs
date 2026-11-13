import assert from 'node:assert/strict'
import test from 'node:test'
import { ApiError, createTransfer } from '../src/api/accounts.js'
import { SAME_ACCOUNT_MESSAGE, validateTransfer } from '../src/lib/transfers.js'

// Replaces fetch with one canned response and records what was requested.
function mockFetch(status, body) {
  const calls = []
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, ...options })
    return { ok: status < 400, status, json: async () => body }
  }
  return calls
}

const valid = { fromAccountId: '1', toAccountId: '2', amount: '40.00', date: '2026-11-21' }

test('validateTransfer accepts two distinct accounts, a positive amount and a date', () => {
  assert.deepEqual(validateTransfer(valid), {})
})

test('validateTransfer rejects the same account on both sides', () => {
  assert.deepEqual(validateTransfer({ ...valid, toAccountId: '1' }), { toAccountId: SAME_ACCOUNT_MESSAGE })
})

test('validateTransfer reports missing and non-positive fields', () => {
  const errors = validateTransfer({ fromAccountId: '', toAccountId: '', amount: '0', date: '' })
  assert.deepEqual(Object.keys(errors), ['fromAccountId', 'toAccountId', 'amount', 'date'])
})

test('createTransfer posts snake_case fields and maps both signed sides', async () => {
  const side = { amount: '40.00', date: '2026-11-21', category: 'other', note: '', kind: 'transfer', transfer_id: 'abc' }
  const calls = mockFetch(201, [
    { ...side, id: 7, account_id: 1, direction: 'out' },
    { ...side, id: 8, account_id: 2, direction: 'in' },
  ])
  const [out, inn] = await createTransfer({ fromAccountId: 1, toAccountId: 2, amount: '40.00', date: '2026-11-21' })

  assert.equal(calls[0].url, '/api/transfers')
  assert.equal(calls[0].method, 'POST')
  assert.deepEqual(JSON.parse(calls[0].body), {
    from_account_id: 1, to_account_id: 2, amount: '40.00', date: '2026-11-21', note: '',
  })
  assert.deepEqual([out.amount, inn.amount], ['-40.00', '40.00'])
  assert.equal(out.transferId, inn.transferId)
})

test('createTransfer rejects with the server error and its field', async () => {
  mockFetch(422, { code: 'invalid_transfer', message: 'the transfer is more than the 80.00 EUR in Wallet', field: 'amount' })
  await assert.rejects(
    createTransfer({ fromAccountId: 3, toAccountId: 1, amount: '500.00', date: '2026-11-21' }),
    (error) => error instanceof ApiError && error.field === 'amount' && error.code === 'invalid_transfer',
  )
})
