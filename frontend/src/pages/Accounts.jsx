import { useState } from 'react'
import {
  createAccount,
  deleteAccount,
  deleteTransaction,
  getNetWorth,
  listAccounts,
  listTransactions,
  renameAccount,
  updateTransaction,
} from '../api/accounts.js'
import AccountForm from '../components/accounts/AccountForm.jsx'
import AccountsTable from '../components/accounts/AccountsTable.jsx'
import ConfirmDialog from '../components/accounts/ConfirmDialog.jsx'
import TransactionsPanel from '../components/accounts/TransactionsPanel.jsx'
import NetWorthCard from '../components/NetWorthCard.jsx'
import SaveStatus from '../components/SaveStatus.jsx'
import { useLoad } from '../hooks/useLoad.js'
import { formatEUR } from '../lib/money.js'

export default function Accounts() {
  const accounts = useLoad(listAccounts, 'accounts')
  const netWorth = useLoad(getNetWorth, 'net-worth')
  const [selectedId, setSelectedId] = useState(null)
  const transactions = useLoad(
    () => (selectedId === null ? Promise.resolve(null) : listTransactions(selectedId)),
    selectedId,
  )

  const [creating, setCreating] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  // { state: 'idle' | 'saving' | 'saved' | 'failed', message }
  const [save, setSave] = useState({ state: 'idle' })
  // { kind: 'account' | 'transaction', item, error }
  const [pendingDelete, setPendingDelete] = useState(null)

  // Every mutation goes through here: on success, balances and the open transaction
  // list are re-read from the API; on failure the caller decides where to show the error.
  async function mutate(action, successText) {
    setBusy(true)
    setSave({ state: 'saving' })
    try {
      const result = await action()
      setSave({ state: 'saved' })
      accounts.reload()
      netWorth.reload()
      transactions.reload()
      setNotice({ kind: 'success', text: successText })
      return { ok: true, result }
    } catch (error) {
      setSave({ state: 'failed', message: error.message })
      if (error.status === 404) {
        accounts.reload()
        netWorth.reload()
        transactions.reload()
      }
      return { ok: false, error }
    } finally {
      setBusy(false)
    }
  }

  async function handleCreate(values) {
    const outcome = await mutate(() => createAccount(values), `Created ${values.name.trim()}.`)
    if (outcome.ok) setCreating(false)
    return outcome
  }

  async function handleRename(id, name) {
    const outcome = await mutate(() => renameAccount(id, name), `Renamed to ${name.trim()}.`)
    return outcome
  }

  async function handleSaveTransaction(accountId, txId, values) {
    return mutate(() => updateTransaction(accountId, txId, values), 'Transaction updated.')
  }

  async function confirmDelete() {
    const { kind, item } = pendingDelete
    const outcome =
      kind === 'account'
        ? await mutate(() => deleteAccount(item.id), `Deleted ${item.name}.`)
        : await mutate(() => deleteTransaction(selectedId, item.id), 'Transaction deleted.')

    if (outcome.ok) {
      if (kind === 'account' && item.id === selectedId) setSelectedId(null)
      setPendingDelete(null)
    } else {
      setPendingDelete({ ...pendingDelete, error: outcome.error.message })
    }
  }

  const selected = accounts.data?.find((a) => a.id === selectedId) ?? null
  const hasAccounts = accounts.data && accounts.data.length > 0

  let list
  if (accounts.status === 'error' && !accounts.data) {
    list = (
      <div className="card state-message state-error" role="alert">
        <h3>Something went wrong</h3>
        <p>{accounts.error?.message}</p>
        <button type="button" className="button" onClick={accounts.reload}>
          Try again
        </button>
      </div>
    )
  } else if (!accounts.data) {
    list = (
      <div role="status">
        <span className="sr-only">Loading accounts…</span>
        <div className="card skeleton skeleton-block short" aria-hidden="true" />
      </div>
    )
  } else if (!hasAccounts) {
    list = (
      <div className="card state-message" role="status">
        <h3>No accounts yet</h3>
        <p>Add your first account, such as a checking account or a wallet, to start tracking balances.</p>
        {!creating && (
          <button type="button" className="button" onClick={() => setCreating(true)}>
            Add account
          </button>
        )}
      </div>
    )
  } else {
    list = (
      <div className="card">
        {accounts.status === 'error' && (
          <p className="field-error" role="alert">
            Balances may be out of date: {accounts.error?.message}{' '}
            <button type="button" className="link-button" onClick={accounts.reload}>
              Try again
            </button>
          </p>
        )}
        <AccountsTable
          accounts={accounts.data}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onRename={handleRename}
          onDelete={(account) => setPendingDelete({ kind: 'account', item: account, error: null })}
        />
      </div>
    )
  }

  return (
    <section className="accounts">
      <div className="page-header">
        <h2>Accounts</h2>
        {hasAccounts && !creating && (
          <button type="button" className="button" onClick={() => setCreating(true)}>
            Add account
          </button>
        )}
      </div>

      <SaveStatus save={save} />

      <div className="notice-slot" role="status">
        {notice && (
          <p className="notice">
            {notice.text}{' '}
            <button type="button" className="link-button" onClick={() => setNotice(null)}>
              Dismiss
            </button>
          </p>
        )}
      </div>

      {hasAccounts && <NetWorthCard net={netWorth} />}

      {creating && <AccountForm onSubmit={handleCreate} onCancel={() => setCreating(false)} busy={busy} />}
      {list}

      {selected && (
        <TransactionsPanel
          key={selected.id}
          account={selected}
          status={transactions.status}
          transactions={transactions.data}
          error={transactions.error}
          onRetry={transactions.reload}
          onSave={handleSaveTransaction}
          onDelete={(tx) => setPendingDelete({ kind: 'transaction', item: tx, error: null })}
        />
      )}

      {pendingDelete && (
        <ConfirmDialog
          title={pendingDelete.kind === 'account' ? `Delete ${pendingDelete.item.name}?` : 'Delete this transaction?'}
          confirmLabel="Delete"
          busy={busy}
          error={pendingDelete.error}
          onConfirm={confirmDelete}
          onCancel={() => setPendingDelete(null)}
        >
          {pendingDelete.kind === 'account' ? (
            <p>
              This removes the account and its {pendingDelete.item.transactionCount} transaction
              {pendingDelete.item.transactionCount === 1 ? '' : 's'}. This cannot be undone.
            </p>
          ) : (
            <p>
              {pendingDelete.item.description}, {formatEUR(pendingDelete.item.amount, { signed: true })}.
              {pendingDelete.item.kind === 'transfer'
                ? ' This also removes the other side of the transfer.'
                : ''}{' '}
              This cannot be undone.
            </p>
          )}
        </ConfirmDialog>
      )}
    </section>
  )
}
