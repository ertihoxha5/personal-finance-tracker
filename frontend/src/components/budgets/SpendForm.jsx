import { useId, useMemo } from 'react'
import { toApi } from '../../api/transactions.js'
import useFormValidation from '../../hooks/useFormValidation.js'
import { CATEGORY_LABELS, toOptions } from '../../lib/labels.js'
import { isoDate, todayISO } from '../../lib/transactions.js'
import { positiveDecimal, required } from '../../lib/validation.js'
import MoneyInput from '../MoneyInput.jsx'
import PageAlert from '../PageAlert.jsx'
import SelectField from '../SelectField.jsx'

// Record an expense from the Budgets screen (#27). It posts the same request as the
// Transactions form; the page then reloads the usage and shows the warnings the API returned.

const CATEGORY_OPTIONS = [{ value: '', label: 'Choose a category…' }, ...toOptions(CATEGORY_LABELS)]

const RULES = {
  accountId: (value) => required(value, 'Choose an account.'),
  category: (value) => required(value, 'Choose a category.'),
  amount: positiveDecimal,
  date: isoDate,
}

export default function SpendForm({ accounts, onSubmit }) {
  const uid = useId()
  const firstAccount = accounts.length === 1 ? String(accounts[0].id) : ''
  const initialValues = useMemo(
    () => ({ accountId: firstAccount, category: '', amount: '', date: todayISO() }),
    [firstAccount],
  )
  const form = useFormValidation({
    initialValues,
    rules: RULES,
    onSubmit: async (values) => {
      // request() already renames the API's account_id to accountId on errors (api/http.js).
      await onSubmit(toApi({ ...values, kind: 'expense', note: '' }))
      form.reset()
    },
  })
  const { values, errors, setValue } = form
  const accountOptions = [
    { value: '', label: 'Choose an account…' },
    ...accounts.map((account) => ({ value: String(account.id), label: account.name })),
  ]

  return (
    <form ref={form.formRef} className="card account-form" noValidate onSubmit={form.handleSubmit}>
      <h3>Record spending</h3>
      <PageAlert alert={form.pageAlert} onDismiss={form.dismissAlert} />
      <div className="form-grid">
        <SelectField
          label="Category"
          name="category"
          value={values.category}
          options={CATEGORY_OPTIONS}
          onChange={(value) => setValue('category', value)}
          error={errors.category ?? null}
        />
        <SelectField
          label="Account"
          name="accountId"
          value={values.accountId}
          options={accountOptions}
          onChange={(value) => setValue('accountId', value)}
          error={errors.accountId ?? null}
        />
        <MoneyInput
          key={form.generation}
          label="Amount"
          name="amount"
          required
          onChange={(_value, text) => setValue('amount', text)}
          error={errors.amount ?? null}
        />
        <div className="field">
          <label htmlFor={`${uid}-date`}>Date</label>
          <input
            id={`${uid}-date`}
            name="date"
            type="date"
            value={values.date}
            onChange={(event) => setValue('date', event.target.value)}
            aria-invalid={Boolean(errors.date)}
            aria-describedby={errors.date ? `${uid}-date-error` : undefined}
          />
          {errors.date && (
            <p id={`${uid}-date-error`} className="field-error">
              {errors.date}
            </p>
          )}
        </div>
      </div>
      <p className="field-hint">An expense counts towards the budget of its category and the month of its date.</p>
      <div className="button-row button-row-start">
        <button type="submit" className="button" disabled={form.submitting} aria-busy={form.submitting}>
          {form.submitting ? 'Saving…' : 'Add expense'}
        </button>
      </div>
    </form>
  )
}
