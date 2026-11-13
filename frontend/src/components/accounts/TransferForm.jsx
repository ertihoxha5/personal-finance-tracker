import { useId, useState } from 'react'
import { todayISO } from '../../lib/transactions.js'
import { validateTransfer } from '../../lib/transfers.js'
import MoneyInput from '../MoneyInput.jsx'
import SelectField from '../SelectField.jsx'
import TextField from '../TextField.jsx'

// Python's Ledger.transfer names fields in snake_case; the form uses camelCase.
const SERVER_FIELD = { from_account_id: 'fromAccountId', to_account_id: 'toAccountId' }

// Transfer between two of the user's accounts (#23). onSubmit(values) resolves
// { ok: true } or { ok: false, error }; an error with a `field` shows under that input.
// The page refreshes both balances after success; this form only collects the values.
export default function TransferForm({ accounts, onSubmit, onCancel, busy }) {
  const uid = useId()
  const [values, setValues] = useState({
    fromAccountId: String(accounts[0]?.id ?? ''),
    toAccountId: String(accounts[1]?.id ?? ''),
    amount: null,
    amountText: '',
    date: todayISO(),
    note: '',
  })
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState(null)

  const set = (field, value) => setValues((current) => ({ ...current, [field]: value }))
  const options = [
    { value: '', label: 'Choose an account' },
    ...accounts.map((a) => ({ value: String(a.id), label: a.name })),
  ]

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError(null)
    const local = validateTransfer({ ...values, amount: values.amountText })
    setErrors(local)
    if (Object.keys(local).length > 0) return

    const result = await onSubmit({
      fromAccountId: Number(values.fromAccountId),
      toAccountId: Number(values.toAccountId),
      amount: values.amount,
      date: values.date,
      note: values.note,
    })
    if (result.ok) return
    const field = SERVER_FIELD[result.error.field] ?? result.error.field
    if (field) setErrors({ [field]: result.error.message })
    else setFormError(result.error.message)
  }

  return (
    <form className="card account-form" onSubmit={handleSubmit} noValidate>
      <h3>Transfer between accounts</h3>
      <p className="field-hint">A transfer moves money between your own accounts. It is not income or expense.</p>
      <div className="form-grid">
        <SelectField
          label="From"
          name="fromAccountId"
          value={values.fromAccountId}
          onChange={(v) => set('fromAccountId', v)}
          options={options}
          error={errors.fromAccountId ?? null}
        />
        <SelectField
          label="To"
          name="toAccountId"
          value={values.toAccountId}
          onChange={(v) => set('toAccountId', v)}
          options={options}
          error={errors.toAccountId ?? null}
        />
        <MoneyInput
          label="Amount"
          name="amount"
          required
          error={errors.amount ?? null}
          onChange={(value, text) => setValues((current) => ({ ...current, amount: value, amountText: text }))}
        />
        <div className="field">
          <label htmlFor={`${uid}-date`}>Date</label>
          <input
            id={`${uid}-date`}
            name="date"
            type="date"
            value={values.date}
            onChange={(e) => set('date', e.target.value)}
            aria-invalid={Boolean(errors.date)}
            aria-describedby={errors.date ? `${uid}-date-error` : undefined}
          />
          {errors.date && (
            <p id={`${uid}-date-error`} className="field-error">
              {errors.date}
            </p>
          )}
        </div>
        <TextField label="Note (optional)" name="note" value={values.note} maxLength={120} onChange={(v) => set('note', v)} />
      </div>
      {formError && (
        <p className="field-error" role="alert">
          {formError}
        </p>
      )}
      <div className="button-row">
        <button type="button" className="button button-secondary" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button type="submit" className="button" disabled={busy}>
          {busy ? 'Transferring…' : 'Transfer'}
        </button>
      </div>
    </form>
  )
}
