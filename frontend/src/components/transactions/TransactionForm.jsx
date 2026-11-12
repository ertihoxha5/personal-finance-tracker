import { useId, useMemo } from 'react'
import useFormValidation from '../../hooks/useFormValidation.js'
import { CATEGORY_LABELS, toOptions } from '../../lib/labels.js'
import { parseMoneyInput } from '../../lib/money.js'
import { isoDate, toDto, todayISO } from '../../lib/transactions.js'
import { positiveDecimal, required } from '../../lib/validation.js'
import MoneyInput from '../MoneyInput.jsx'
import PageAlert from '../PageAlert.jsx'
import SelectField from '../SelectField.jsx'
import TextField from '../TextField.jsx'

// Shared income/expense form (#14): kind, account, amount, date, category and note.
// Validation, server errors and the double-submit guard come from useFormValidation
// (#12). onSubmit(dto) receives the request body from toDto and may throw an API error;
// the form clears after it resolves. Transfers use their own form (a later task).

const KIND_CHOICES = [
  { value: 'expense', label: 'Expense' },
  { value: 'income', label: 'Income' },
]

const CATEGORY_OPTIONS = [{ value: '', label: 'Choose a category…' }, ...toOptions(CATEGORY_LABELS)]

const RULES = {
  accountId: (value) => required(value, 'Choose an account.'),
  amount: positiveDecimal,
  date: isoDate,
  category: (value) => required(value, 'Choose a category.'),
  note: () => null,
}

// Server errors use the API field names; map them onto this form's fields.
const SERVER_FIELDS = { account_id: 'accountId' }

export default function TransactionForm({ accounts, onSubmit, defaultAccountId = '', title = 'New transaction' }) {
  const uid = useId()
  const initialValues = useMemo(
    () => ({
      kind: 'expense',
      accountId: defaultAccountId === '' ? '' : String(defaultAccountId),
      amount: '',
      date: todayISO(),
      category: '',
      note: '',
    }),
    [defaultAccountId],
  )

  const form = useFormValidation({
    initialValues,
    rules: RULES,
    onSubmit: async (values) => {
      try {
        await onSubmit(toDto({ ...values, amount: parseMoneyInput(values.amount).value }))
      } catch (error) {
        throw renameFields(error)
      }
      form.reset()
    },
  })

  const accountOptions = [
    { value: '', label: 'Choose an account…' },
    ...accounts.map((account) => ({ value: String(account.id), label: account.name })),
  ]
  const { values, errors, setValue } = form

  return (
    <form ref={form.formRef} className="card transaction-form" noValidate onSubmit={form.handleSubmit}>
      <h3>{title}</h3>
      <PageAlert alert={form.pageAlert} onDismiss={form.dismissAlert} />

      <fieldset className="kind-choice">
        <legend>Type</legend>
        {KIND_CHOICES.map((choice) => (
          <label key={choice.value} className="radio-option">
            <input
              type="radio"
              name="kind"
              value={choice.value}
              checked={values.kind === choice.value}
              onChange={() => setValue('kind', choice.value)}
            />
            {choice.label}
          </label>
        ))}
      </fieldset>

      <div className="form-grid">
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
        <SelectField
          label="Category"
          name="category"
          value={values.category}
          options={CATEGORY_OPTIONS}
          onChange={(value) => setValue('category', value)}
          error={errors.category ?? null}
        />
        <TextField
          label="Note (optional)"
          name="note"
          value={values.note}
          maxLength={200}
          onChange={(value) => setValue('note', value)}
          error={errors.note ?? null}
        />
      </div>

      <div className="button-row button-row-start">
        <button type="submit" className="button" disabled={form.submitting} aria-busy={form.submitting}>
          {form.submitting ? 'Saving…' : `Add ${values.kind}`}
        </button>
      </div>
    </form>
  )
}

function renameFields(error) {
  // A plain object, not a spread: an Error's message is not an enumerable property.
  const rename = (item) =>
    item && typeof item === 'object' && Object.hasOwn(SERVER_FIELDS, item.field ?? '')
      ? { code: item.code, message: item.message, field: SERVER_FIELDS[item.field], status: item.status }
      : item
  if (Array.isArray(error)) return error.map(rename)
  if (error && typeof error === 'object' && Array.isArray(error.errors)) return { ...error, errors: error.errors.map(rename) }
  return rename(error)
}
