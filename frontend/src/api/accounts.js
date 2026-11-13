// Accounts API client (#18): talks to FastAPI (pft/api/accounts.py), which keeps the data in
// SQLite. Components keep the same function names and shapes as before:
//   - IDs are integers assigned by the server;
//   - amounts are decimal strings, and balances and net worth are calculated by the server;
//   - a failure rejects with an ApiError carrying the message, the input field it belongs to
//     (or null), and the HTTP status.
// The API sends domain transactions (note, category, unsigned amount, kind/direction). The
// Accounts screen works with a description and a signed amount, so toTransaction() does that
// one translation here, as a string operation (never through Number()).

import { ApiError, request } from './http.js'

export { ApiError }

const toAccount = (dto) => ({
  id: dto.id,
  name: dto.name,
  type: dto.type,
  openingBalance: dto.opening_balance,
  currency: dto.currency,
  balance: dto.balance,
  transactionCount: dto.transaction_count,
})

const isNegative = (dto) => dto.kind === 'expense' || (dto.kind === 'transfer' && dto.direction === 'out')

// A transfer's other leg is found by its shared transferId, so the panel can say both
// sides change together. The description falls back to the category when there is no note.
const toTransaction = (dto) => ({
  id: dto.id,
  accountId: dto.account_id,
  date: dto.date,
  description: dto.note || dto.category,
  category: dto.category,
  kind: dto.kind,
  amount: isNegative(dto) ? `-${dto.amount}` : dto.amount,
  transferId: dto.transfer_id,
})

export async function listAccounts() {
  return (await request('/accounts')).map(toAccount)
}

export async function getNetWorth() {
  const dto = await request('/net-worth')
  return { currency: dto.currency, netWorth: dto.net_worth, accountCount: dto.account_count }
}

export async function createAccount({ name, type, openingBalance }) {
  if (openingBalance === null || openingBalance === undefined) {
    throw new ApiError('Enter an opening balance. Use 0 for a new account.', { field: 'openingBalance' })
  }
  const dto = await request('/accounts', {
    method: 'POST',
    body: { name, type, opening_balance: openingBalance },
  })
  return toAccount(dto)
}

export async function renameAccount(id, name) {
  return toAccount(await request(`/accounts/${id}`, { method: 'PATCH', body: { name } }))
}

export async function deleteAccount(id) {
  return request(`/accounts/${id}`, { method: 'DELETE' })
}

export async function listTransactions(accountId) {
  return (await request(`/accounts/${accountId}/transactions`)).map(toTransaction)
}

// Edit by stable ID. `amount` is a positive decimal string; the server works out the sign
// from the kind. Transfers are edited as a linked pair, which the server does not offer yet.
export async function updateTransaction(accountId, txId, { date, description, kind, amount }) {
  const dto = await request(`/accounts/${accountId}/transactions/${txId}`, {
    method: 'PUT',
    body: { kind, amount, date, note: description },
  })
  return toTransaction(dto)
}

export async function deleteTransaction(accountId, txId) {
  return request(`/accounts/${accountId}/transactions/${txId}`, { method: 'DELETE' })
}

// Move money between two accounts (#23). The server's Ledger.transfer adds both sides (OUT on
// the source, IN on the destination, one shared transfer_id) or neither, and rejects the same
// account twice or a source that would go below zero. Resolves with [outSide, inSide].
// Transfers are not income or expense, so only the two balances change; net worth stays the same.
export async function createTransfer({ fromAccountId, toAccountId, amount, date, note = '' }) {
  const sides = await request('/transfers', {
    method: 'POST',
    body: { from_account_id: fromAccountId, to_account_id: toAccountId, amount, date, note },
  })
  return sides.map(toTransaction)
}
