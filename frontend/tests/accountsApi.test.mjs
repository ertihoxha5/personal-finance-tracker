import assert from 'node:assert/strict'
import test from 'node:test'
import { ApiError, getNetWorth, listAccounts, listTransactions, renameAccount } from '../src/api/accounts.js'

// Replaces fetch with one canned response and records what was requested.
function mockFetch(status, body) {
  const calls = []
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, ...options })
    return { ok: status < 400, status, json: async () => body }
  }
  return calls
}

test('accounts keep the server balance string untouched', async () => {
  mockFetch(200, [
    { id: 1, name: 'Checking', type: 'bank', opening_balance: '1500.00', currency: 'EUR', balance: '3035.50', transaction_count: 3 },
  ])
  const [account] = await listAccounts()
  assert.deepEqual(account, {
    id: 1, name: 'Checking', type: 'bank', openingBalance: '1500.00', currency: 'EUR',
    balance: '3035.50', transactionCount: 3,
  })
})

test('net worth comes from the API response', async () => {
  mockFetch(200, { currency: 'EUR', net_worth: '8035.50', account_count: 2 })
  assert.deepEqual(await getNetWorth(), { currency: 'EUR', netWorth: '8035.50', accountCount: 2 })
})

test('transactions get a description and a sign without touching the digits', async () => {
  mockFetch(200, [
    { id: 2, account_id: 1, kind: 'expense', amount: '64.50', date: '2026-11-02', category: 'food', note: 'Groceries', transfer_id: null, direction: null },
    { id: 3, account_id: 1, kind: 'income', amount: '0.10', date: '2026-11-03', category: 'salary', note: '', transfer_id: null, direction: null },
    { id: 4, account_id: 1, kind: 'transfer', amount: '5.00', date: '2026-11-04', category: 'other', note: '', transfer_id: 't-1', direction: 'out' },
  ])
  const txs = await listTransactions(1)
  assert.deepEqual(txs.map((t) => [t.description, t.amount]), [
    ['Groceries', '-64.50'],
    ['salary', '0.10'],
    ['other', '-5.00'],
  ])
})

test('a domain error becomes an ApiError with the field renamed for the form', async () => {
  mockFetch(422, { code: 'invalid_account_name', message: 'account name must not be empty', field: 'name' })
  await assert.rejects(renameAccount(1, ' '), (error) => {
    assert.ok(error instanceof ApiError)
    assert.equal(error.status, 422)
    assert.equal(error.field, 'name')
    assert.equal(error.code, 'invalid_account_name')
    return true
  })
})

test('a network failure is reported as an unreachable server', async () => {
  globalThis.fetch = async () => {
    throw new TypeError('fetch failed')
  }
  await assert.rejects(listAccounts(), (error) => error instanceof ApiError && error.status === 0)
})

test('renaming sends a PATCH with the new name as JSON', async () => {
  const calls = mockFetch(200, { id: 1, name: 'Main', type: 'bank', opening_balance: '0.00', currency: 'EUR', balance: '0.00', transaction_count: 0 })
  await renameAccount(1, 'Main')
  assert.equal(calls[0].url, '/api/accounts/1')
  assert.equal(calls[0].method, 'PATCH')
  assert.deepEqual(JSON.parse(calls[0].body), { name: 'Main' })
})
