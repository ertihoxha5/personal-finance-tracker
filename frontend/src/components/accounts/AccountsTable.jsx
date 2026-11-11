import { useState } from 'react'
import { ACCOUNT_TYPES } from '../../fixtures/accounts.js'
import { formatEUR } from '../../lib/money.js'

const TYPE_LABELS = Object.fromEntries(ACCOUNT_TYPES.map((t) => [t.value, t.label]))

function RenameCell({ account, onRename, onDone }) {
  const [name, setName] = useState(account.name)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    const result = await onRename(account.id, name)
    setBusy(false)
    if (result.ok) onDone()
    else setError(result.error.message)
  }

  return (
    <form className="rename-form" onSubmit={handleSubmit} noValidate>
      <label className="sr-only" htmlFor={`rename-${account.id}`}>
        New name for {account.name}
      </label>
      <input
        id={`rename-${account.id}`}
        type="text"
        value={name}
        maxLength={80}
        autoFocus
        onChange={(e) => setName(e.target.value)}
        aria-invalid={error !== null}
        aria-describedby={error ? `rename-${account.id}-error` : undefined}
        onKeyDown={(e) => e.key === 'Escape' && onDone()}
      />
      <button type="submit" className="button button-small" disabled={busy}>
        Save
      </button>
      <button type="button" className="button button-secondary button-small" onClick={onDone} disabled={busy}>
        Cancel
      </button>
      {error && (
        <p id={`rename-${account.id}-error`} className="field-error" role="alert">
          {error}
        </p>
      )}
    </form>
  )
}

export default function AccountsTable({ accounts, selectedId, onSelect, onRename, onDelete }) {
  const [renamingId, setRenamingId] = useState(null)

  return (
    <div className="table-scroll">
      <table className="data-table stack-narrow">
        <caption className="sr-only">Accounts with opening and current balance</caption>
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">Type</th>
            <th scope="col" className="num">
              Opening balance
            </th>
            <th scope="col" className="num">
              Current balance
            </th>
            <th scope="col">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {accounts.map((account) => (
            <tr key={account.id} aria-selected={account.id === selectedId}>
              <th scope="row">
                {renamingId === account.id ? (
                  <RenameCell account={account} onRename={onRename} onDone={() => setRenamingId(null)} />
                ) : (
                  account.name
                )}
              </th>
              <td data-label="Type">{TYPE_LABELS[account.type] ?? account.type}</td>
              <td className="num" data-label="Opening balance">{formatEUR(account.openingBalance)}</td>
              <td className={`num ${account.balance.startsWith('-') ? 'amount-expense' : ''}`} data-label="Current balance">
                {formatEUR(account.balance)}
              </td>
              <td>
                <div className="row-actions">
                  <button
                    type="button"
                    className="button button-secondary button-small"
                    aria-pressed={account.id === selectedId}
                    onClick={() => onSelect(account.id === selectedId ? null : account.id)}
                  >
                    Transactions
                    <span className="sr-only"> for {account.name}</span>
                  </button>
                  <button
                    type="button"
                    className="button button-secondary button-small"
                    onClick={() => setRenamingId(account.id)}
                  >
                    Rename<span className="sr-only"> {account.name}</span>
                  </button>
                  <button
                    type="button"
                    className="button button-secondary button-small"
                    onClick={() => onDelete(account)}
                  >
                    Delete<span className="sr-only"> {account.name}</span>
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
