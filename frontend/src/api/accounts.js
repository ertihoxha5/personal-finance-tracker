import { ACCOUNT_SEED, ACCOUNT_TYPES } from '../fixtures/accounts.js'

// Stage B data source, like api/dashboard.js: an in-memory stand-in for the accounts API
// so the screen can be built before #11/#18 expose real endpoints. It keeps the same
// contract the real API should follow:
//   - IDs are stable integers assigned by the server and never reused or changed;
//   - amounts are decimal strings, and balances are calculated here, not in React;
//   - failures reject with an ApiError carrying a message and, when it belongs to one
//     input, the name of that field.
// When the real endpoints exist, replace the bodies with fetch() and keep the signatures.
//
// Preview other states by adding to the page URL:
//   ?state=loading | empty | error      (list loading)
//   ?state=mutation-error               (every create/rename/edit/delete fails)

const DELAY_MS = 250
const MAX_NAME_LENGTH = 60

export class ApiError extends Error {
  constructor(message, { field = null, status = 400 } = {}) {
    super(message)
    this.name = 'ApiError'
    this.field = field
    this.status = status
  }
}

let db = structuredClone(ACCOUNT_SEED)
let nextAccountId = 5

const previewState = () => new URLSearchParams(window.location.search).get('state')

function respond(compute) {
  const state = previewState()
  if (state === 'loading') return new Promise(() => {})
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      try {
        resolve(structuredClone(compute()))
      } catch (error) {
        reject(error)
      }
    }, DELAY_MS)
  })
}

function respondToMutation(compute) {
  return respond(() => {
    if (previewState() === 'mutation-error') {
      throw new ApiError('The server could not save that change. Nothing was changed.', { status: 500 })
    }
    return compute()
  })
}

// Integer cents keep the stand-in exact, as the Python Money type does.
const toCents = (text) => {
  const negative = text.startsWith('-')
  const [whole, fraction = ''] = text.replace('-', '').split('.')
  const cents = Number(whole) * 100 + Number(`${fraction}00`.slice(0, 2))
  return negative ? -cents : cents
}

const fromCents = (cents) => {
  const abs = Math.abs(cents)
  return `${cents < 0 ? '-' : ''}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`
}

function withBalance(account) {
  const total = db.transactions
    .filter((t) => t.accountId === account.id)
    .reduce((sum, t) => sum + toCents(t.amount), toCents(account.openingBalance))
  return {
    ...account,
    balance: fromCents(total),
    transactionCount: db.transactions.filter((t) => t.accountId === account.id).length,
  }
}

function requireAccount(id) {
  const account = db.accounts.find((a) => a.id === id)
  if (!account) throw new ApiError('That account no longer exists. Refresh the list.', { status: 404 })
  return account
}

function requireTransaction(accountId, txId) {
  const tx = db.transactions.find((t) => t.id === txId && t.accountId === accountId)
  if (!tx) throw new ApiError('That transaction no longer exists. Refresh the list.', { status: 404 })
  return tx
}

function validateName(raw, ignoreId = null) {
  const name = raw.trim()
  if (!name) throw new ApiError('Enter a name for the account.', { field: 'name' })
  if (name.length > MAX_NAME_LENGTH) {
    throw new ApiError(`Use ${MAX_NAME_LENGTH} characters or fewer.`, { field: 'name' })
  }
  const taken = db.accounts.some((a) => a.id !== ignoreId && a.name.toLowerCase() === name.toLowerCase())
  if (taken) throw new ApiError('You already have an account with that name.', { field: 'name' })
  return name
}

export function listAccounts() {
  return respond(() => {
    const state = previewState()
    if (state === 'error') throw new ApiError('The accounts could not be loaded.', { status: 500 })
    if (state === 'empty') return []
    return db.accounts.map(withBalance)
  })
}

export function createAccount({ name, type, openingBalance }) {
  return respondToMutation(() => {
    const cleanName = validateName(name)
    if (!ACCOUNT_TYPES.some((t) => t.value === type)) {
      throw new ApiError('Choose an account type.', { field: 'type' })
    }
    if (openingBalance === null || openingBalance === undefined) {
      throw new ApiError('Enter an opening balance. Use 0 for a new account.', { field: 'openingBalance' })
    }
    const account = { id: nextAccountId++, name: cleanName, type, openingBalance }
    db.accounts.push(account)
    return withBalance(account)
  })
}

export function renameAccount(id, name) {
  return respondToMutation(() => {
    const account = requireAccount(id)
    account.name = validateName(name, id)
    return withBalance(account)
  })
}

export function deleteAccount(id) {
  return respondToMutation(() => {
    requireAccount(id)
    // Transfers keep a counterpart leg in another account, so the whole transfer goes.
    const doomed = new Set(db.transactions.filter((t) => t.accountId === id).map((t) => t.id))
    db.transactions.forEach((t) => {
      if (doomed.has(t.id) && t.counterpartId) doomed.add(t.counterpartId)
    })
    db.transactions = db.transactions.filter((t) => !doomed.has(t.id))
    db.accounts = db.accounts.filter((a) => a.id !== id)
    return { id }
  })
}

export function listTransactions(accountId) {
  return respond(() => {
    requireAccount(accountId)
    return db.transactions
      .filter((t) => t.accountId === accountId)
      .sort((a, b) => b.date.localeCompare(a.date) || b.id - a.id)
  })
}

// Edit by stable ID. `amount` is a positive decimal string; the sign comes from the kind,
// except transfers, which keep their direction. A transfer updates both legs together or
// not at all, so the two balances can never disagree (FR-04).
export function updateTransaction(accountId, txId, { date, description, kind, amount }) {
  return respondToMutation(() => {
    const tx = requireTransaction(accountId, txId)
    const cleanDescription = description.trim()
    if (!cleanDescription) throw new ApiError('Enter a description.', { field: 'description' })
    if (!date) throw new ApiError('Choose a date.', { field: 'date' })
    if (amount === null || amount === undefined || toCents(amount) === 0) {
      throw new ApiError('Enter an amount greater than zero.', { field: 'amount' })
    }

    const cents = toCents(amount)
    let signed
    if (tx.kind === 'transfer') signed = toCents(tx.amount) < 0 ? -cents : cents
    else if (kind === 'income') signed = cents
    else if (kind === 'expense') signed = -cents
    else throw new ApiError('Choose income or expense.', { field: 'kind' })

    const legs = tx.counterpartId ? [tx, db.transactions.find((t) => t.id === tx.counterpartId)] : [tx]
    legs.forEach((leg, index) => {
      leg.date = date
      leg.description = cleanDescription
      leg.amount = fromCents(index === 0 ? signed : -signed)
      if (tx.kind !== 'transfer') leg.kind = kind
    })
    return tx
  })
}

export function deleteTransaction(accountId, txId) {
  return respondToMutation(() => {
    const tx = requireTransaction(accountId, txId)
    const removed = new Set([tx.id, tx.counterpartId].filter(Boolean))
    db.transactions = db.transactions.filter((t) => !removed.has(t.id))
    return { id: txId }
  })
}
