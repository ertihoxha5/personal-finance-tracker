import { useId, useMemo } from 'react'
import useFormValidation from '../../hooks/useFormValidation.js'
import { CATEGORY_LABELS, toOptions } from '../../lib/labels.js'
import { positiveDecimal, required } from '../../lib/validation.js'
import MoneyInput from '../MoneyInput.jsx'
import PageAlert from '../PageAlert.jsx'
import SelectField from '../SelectField.jsx'

// Set a budget (#27): category, month and limit. Saving the same category and month again
// replaces the limit. onSubmit(values) may throw an API error; errors for category, month
// or limit show under that input (the API uses the same field names).

const CATEGORY_OPTIONS = [{ value: '', label: 'Choose a category…' }, ...toOptions(CATEGORY_LABELS)]
const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/

const RULES = {
  category: (value) => required(value, 'Choose a category.'),
  month: (value) => (MONTH.test(String(value ?? '')) ? null : 'Choose a month like 2026-11.'),
  limit: positiveDecimal,
}

export default function BudgetForm({ month, onSubmit }) {
  const uid = useId()
  const initialValues = useMemo(() => ({ category: '', month, limit: '' }), [month])
  const form = useFormValidation({
    initialValues,
    rules: RULES,
    onSubmit: async (values) => {
      await onSubmit(values)
      form.reset()
    },
  })
  const { values, errors, setValue } = form

  return (
    <form ref={form.formRef} className="card account-form" noValidate onSubmit={form.handleSubmit}>
      <h3>Set a budget</h3>
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
        <div className="field">
          <label htmlFor={`${uid}-month`}>Month</label>
          <input
            id={`${uid}-month`}
            name="month"
            type="month"
            value={values.month}
            onChange={(event) => setValue('month', event.target.value)}
            aria-invalid={Boolean(errors.month)}
            aria-describedby={errors.month ? `${uid}-month-error` : undefined}
          />
          {errors.month && (
            <p id={`${uid}-month-error`} className="field-error">
              {errors.month}
            </p>
          )}
        </div>
        <MoneyInput
          key={form.generation}
          label="Monthly limit"
          name="limit"
          required
          onChange={(_value, text) => setValue('limit', text)}
          error={errors.limit ?? null}
        />
      </div>
      <p className="field-hint">Saving a category and month that already has a budget replaces its limit.</p>
      <div className="button-row button-row-start">
        <button type="submit" className="button" disabled={form.submitting} aria-busy={form.submitting}>
          {form.submitting ? 'Saving…' : 'Save budget'}
        </button>
      </div>
    </form>
  )
}
