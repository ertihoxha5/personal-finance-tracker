import { useId, useState } from 'react'
import MoneyInput from '../MoneyInput.jsx'
import { ACCOUNT_TYPES } from '../../fixtures/accounts.js'

// Create-account form. onSubmit(values) resolves { ok: true } or { ok: false, error };
// an error with a `field` is shown under that input, any other error above the buttons.
export default function AccountForm({ onSubmit, onCancel, busy }) {
  const uid = useId()
  const [name, setName] = useState('')
  const [type, setType] = useState('bank')
  const [openingBalance, setOpeningBalance] = useState(null)
  const [error, setError] = useState(null)

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    const result = await onSubmit({ name, type, openingBalance })
    if (!result.ok) setError(result.error)
  }

  const fieldError = (field) => (error?.field === field ? error.message : null)
  const nameError = fieldError('name')

  return (
    <form className="card account-form" onSubmit={handleSubmit} noValidate>
      <h3>New account</h3>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${uid}-name`}>Name</label>
          <input
            id={`${uid}-name`}
            type="text"
            value={name}
            maxLength={80}
            onChange={(e) => setName(e.target.value)}
            aria-invalid={nameError !== null}
            aria-describedby={nameError ? `${uid}-name-error` : undefined}
            autoFocus
          />
          {nameError && (
            <p id={`${uid}-name-error`} className="field-error">
              {nameError}
            </p>
          )}
        </div>
        <div className="field">
          <label htmlFor={`${uid}-type`}>Type</label>
          <select id={`${uid}-type`} value={type} onChange={(e) => setType(e.target.value)}>
            {ACCOUNT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <MoneyInput
            label="Opening balance"
            hint="Use 0 for a new account, or a negative amount such as -250.00 for an existing debt."
            required
            allowNegative
            onChange={setOpeningBalance}
          />
          {fieldError('openingBalance') && <p className="field-error">{fieldError('openingBalance')}</p>}
        </div>
      </div>
      {error && !error.field && (
        <p className="field-error" role="alert">
          {error.message}
        </p>
      )}
      <div className="button-row">
        <button type="button" className="button button-secondary" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button type="submit" className="button" disabled={busy}>
          {busy ? 'Creating…' : 'Create account'}
        </button>
      </div>
    </form>
  )
}
