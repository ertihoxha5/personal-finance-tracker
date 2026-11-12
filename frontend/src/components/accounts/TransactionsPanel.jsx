import { useId, useState } from 'react'
import MoneyInput from '../MoneyInput.jsx'
import { KIND_LABELS } from '../../fixtures/accounts.js'
import { formatDate } from '../../lib/format.js'
import { formatEUR } from '../../lib/money.js'

const unsigned = (amount) => amount.replace('-', '')

function EditRow({ tx, onSave, onCancel }) {
  const uid = useId()
  const [date, setDate] = useState(tx.date)
  const [description, setDescription] = useState(tx.description)
  const [kind, setKind] = useState(tx.kind)
  const [amount, setAmount] = useState(unsigned(tx.amount))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const isTransfer = tx.kind === 'transfer'

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    const result = await onSave(tx.id, { date, description, kind, amount })
    setBusy(false)
    if (!result.ok) setError(result.error)
  }

  const fieldError = (field) => (error?.field === field ? error.message : null)

  return (
    <tr>
      <td colSpan={5}>
        <form className="inline-form" onSubmit={handleSubmit} noValidate>
          <div className="form-grid">
            <div className="field">
              <label htmlFor={`${uid}-date`}>Date</label>
              <input
                id={`${uid}-date`}
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                aria-invalid={fieldError('date') !== null}
              />
              {fieldError('date') && <p className="field-error">{fieldError('date')}</p>}
            </div>
            <div className="field">
              <label htmlFor={`${uid}-desc`}>Description</label>
              <input
                id={`${uid}-desc`}
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                aria-invalid={fieldError('description') !== null}
                autoFocus
              />
              {fieldError('description') && <p className="field-error">{fieldError('description')}</p>}
            </div>
            <div className="field">
              <label htmlFor={`${uid}-kind`}>Type</label>
              <select
                id={`${uid}-kind`}
                value={kind}
                onChange={(e) => setKind(e.target.value)}
                disabled={isTransfer}
              >
                {isTransfer ? (
                  <option value="transfer">Transfer</option>
                ) : (
                  <>
                    <option value="expense">Expense</option>
                    <option value="income">Income</option>
                  </>
                )}
              </select>
            </div>
            <div>
              <MoneyInput label="Amount" defaultValue={unsigned(tx.amount)} required onChange={setAmount} />
              {fieldError('amount') && <p className="field-error">{fieldError('amount')}</p>}
            </div>
          </div>
          {isTransfer && (
            <p className="field-hint">Transfers cannot be edited yet: both sides must change together, which is not available.</p>
          )}
          {error && !error.field && (
            <p className="field-error" role="alert">
              {error.message}
            </p>
          )}
          <div className="button-row">
            <button type="button" className="button button-secondary button-small" onClick={onCancel} disabled={busy}>
              Cancel
            </button>
            <button type="submit" className="button button-small" disabled={busy}>
              {busy ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </form>
      </td>
    </tr>
  )
}

export default function TransactionsPanel({ account, status, transactions, error, onRetry, onSave, onDelete }) {
  const [editingId, setEditingId] = useState(null)

  async function handleSave(id, values) {
    const result = await onSave(account.id, id, values)
    if (result.ok) setEditingId(null)
    return result
  }

  let body
  if (status === 'error' && !transactions) {
    body = (
      <div className="state-message state-error" role="alert">
        <p>{error?.message ?? 'The transactions could not be loaded.'}</p>
        <button type="button" className="button" onClick={onRetry}>
          Try again
        </button>
      </div>
    )
  } else if (!transactions) {
    body = (
      <div role="status">
        <span className="sr-only">Loading transactions…</span>
        <div className="skeleton skeleton-block short" aria-hidden="true" />
      </div>
    )
  } else if (transactions.length === 0) {
    body = (
      <div className="state-message" role="status">
        <h4>No transactions yet</h4>
        <p>{account.name} has no transactions. Its balance equals its opening balance.</p>
      </div>
    )
  } else {
    body = (
      <div className="table-scroll">
        <table className="data-table stack-narrow">
          <caption className="sr-only">Transactions in {account.name}</caption>
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">Description</th>
              <th scope="col">Type</th>
              <th scope="col" className="num">
                Amount
              </th>
              <th scope="col">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((tx) =>
              editingId === tx.id ? (
                <EditRow key={tx.id} tx={tx} onSave={handleSave} onCancel={() => setEditingId(null)} />
              ) : (
                <tr key={tx.id}>
                  <td data-label="Date">{formatDate(tx.date)}</td>
                  <th scope="row">{tx.description}</th>
                  <td data-label="Type">{KIND_LABELS[tx.kind] ?? tx.kind}</td>
                  <td className={`num ${tx.amount.startsWith('-') ? 'amount-expense' : 'amount-income'}`} data-label="Amount">
                    {formatEUR(tx.amount, { signed: true })}
                  </td>
                  <td>
                    <div className="row-actions">
                      <button
                        type="button"
                        className="button button-secondary button-small"
                        onClick={() => setEditingId(tx.id)}
                      >
                        Edit<span className="sr-only"> {tx.description}</span>
                      </button>
                      <button
                        type="button"
                        className="button button-secondary button-small"
                        onClick={() => onDelete(tx)}
                      >
                        Delete<span className="sr-only"> {tx.description}</span>
                      </button>
                    </div>
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <section className="card" aria-labelledby="tx-heading">
      <h3 id="tx-heading">Transactions in {account.name}</h3>
      {body}
    </section>
  )
}
