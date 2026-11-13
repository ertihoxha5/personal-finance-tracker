import { useId, useMemo } from 'react'
import useFormValidation from '../../hooks/useFormValidation.js'
import { RECURRING_FIELD_TO_FORM, toRecurringApi } from '../../api/recurring.js'
import { API_TO_FORM_FIELD, toApi } from '../../api/transactions.js'
import { CATEGORY_LABELS, FREQUENCY_LABELS, toOptions } from '../../lib/labels.js'
import { isoDate, todayISO } from '../../lib/transactions.js'
import { positiveDecimal, required } from '../../lib/validation.js'
import MoneyInput from '../MoneyInput.jsx'
import PageAlert from '../PageAlert.jsx'
import RecurrencePreview from './RecurrencePreview.jsx'
import SelectField from '../SelectField.jsx'
import TextField from '../TextField.jsx'

// Shared income/expense form (#14): kind, account, amount, date, category and note.
// Validation, server errors and the double-submit guard come from useFormValidation
// (#12). onSubmit(dto) receives the request body from toApi (#17) and may throw an API error;
// the form clears after it resolves. Transfers use their own form (#23).
//
// With onSubmitRecurring (#25) the form also offers Repeat: weekly, monthly or yearly.
// The date then becomes the start date, an optional end date appears, and the upcoming
// dates are previewed from the server. onSubmitRecurring(body) gets toRecurringApi().

const KIND_CHOICES = [
  { value: 'expense', label: 'Expense' },
  { value: 'income', label: 'Income' },
]

const CATEGORY_OPTIONS = [{ value: '', label: 'Choose a category…' }, ...toOptions(CATEGORY_LABELS)]
const REPEAT_OPTIONS = [{ value: '', label: 'Does not repeat' }, ...toOptions(FREQUENCY_LABELS)]
const FIELD_NAMES = { ...API_TO_FORM_FIELD, ...RECURRING_FIELD_TO_FORM }

const RULES = {
  accountId: (value) => required(value, 'Choose an account.'),
  amount: positiveDecimal,
  date: isoDate,
  category: (value) => required(value, 'Choose a category.'),
  note: () => null,
  frequency: () => null,
  endDate: (value) => (value ? isoDate(value) : null),
}

export default function TransactionForm({
  accounts,
  onSubmit,
  onSubmitRecurring = null,
  defaultAccountId = '',
  title = 'New transaction',
}) {
  const uid = useId()
  const initialValues = useMemo(
    () => ({
      kind: 'expense',
      accountId: defaultAccountId === '' ? '' : String(defaultAccountId),
      amount: '',
      date: todayISO(),
      category: '',
      note: '',
      frequency: '',
      endDate: '',
    }),
    [defaultAccountId],
  )

  const form = useFormValidation({
    initialValues,
    rules: RULES,
    onSubmit: async (values) => {
      try {
        if (values.frequency && onSubmitRecurring) await onSubmitRecurring(toRecurringApi(values))
        else await onSubmit(toApi(values))
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
  const repeats = Boolean(onSubmitRecurring && values.frequency)

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
          <label htmlFor={`${uid}-date`}>{repeats ? 'Start date' : 'Date'}</label>
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
        {onSubmitRecurring && (
          <SelectField
            label="Repeat"
            name="frequency"
            value={values.frequency}
            options={REPEAT_OPTIONS}
            onChange={(value) => setValue('frequency', value)}
            error={errors.frequency ?? null}
          />
        )}
        {repeats && (
          <div className="field">
            <label htmlFor={`${uid}-end`}>End date (optional)</label>
            <input
              id={`${uid}-end`}
              name="endDate"
              type="date"
              value={values.endDate}
              min={values.date || undefined}
              onChange={(event) => setValue('endDate', event.target.value)}
              aria-invalid={Boolean(errors.endDate)}
              aria-describedby={errors.endDate ? `${uid}-end-error` : undefined}
            />
            {errors.endDate && (
              <p id={`${uid}-end-error`} className="field-error">
                {errors.endDate}
              </p>
            )}
          </div>
        )}
        <TextField
          label="Note (optional)"
          name="note"
          value={values.note}
          maxLength={200}
          onChange={(value) => setValue('note', value)}
          error={errors.note ?? null}
        />
      </div>

      {repeats && <RecurrencePreview frequency={values.frequency} startDate={values.date} endDate={values.endDate} />}

      <div className="button-row button-row-start">
        <button type="submit" className="button" disabled={form.submitting} aria-busy={form.submitting}>
          {form.submitting ? 'Saving…' : repeats ? `Save ${values.frequency} ${values.kind}` : `Add ${values.kind}`}
        </button>
      </div>
    </form>
  )
}

// Server errors use the API field names; map them onto this form's fields (FIELD_NAMES).
function renameFields(error) {
  // A plain object, not a spread: an Error's message is not an enumerable property.
  const rename = (item) =>
    item && typeof item === 'object' && Object.hasOwn(FIELD_NAMES, item.field ?? '')
      ? { code: item.code, message: item.message, field: FIELD_NAMES[item.field], status: item.status }
      : item
  if (Array.isArray(error)) return error.map(rename)
  if (error && typeof error === 'object' && Array.isArray(error.errors)) return { ...error, errors: error.errors.map(rename) }
  return rename(error)
}
