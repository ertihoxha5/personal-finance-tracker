import { useState } from 'react'
import MoneyInput from '../components/MoneyInput.jsx'
import PageAlert from '../components/PageAlert.jsx'
import SelectField from '../components/SelectField.jsx'
import { CATEGORY_ERROR, FIELD_ERROR, MULTIPLE_ERRORS, PAGE_ERROR, SERVER_ERROR } from '../fixtures/apiErrors.js'
import { mapApiError } from '../lib/apiErrors.js'
import {
  ACCOUNT_TYPE_LABELS,
  CATEGORY_LABELS,
  FREQUENCY_LABELS,
  KIND_LABELS,
  categoryLabel,
  toOptions,
} from '../lib/labels.js'

// Development-only demo for #10: inline field errors, the recoverable page alert and
// the enum labels, all driven by fixture errors. Registered in App.jsx only in DEV.

const SCENARIOS = [
  { id: 'fields', label: 'Field errors + page error', error: MULTIPLE_ERRORS },
  { id: 'amount', label: 'Amount error only', error: FIELD_ERROR },
  { id: 'category', label: 'Category error only', error: CATEGORY_ERROR },
  { id: 'page', label: 'Not found (no retry)', error: PAGE_ERROR },
  { id: 'server', label: 'Server error (500)', error: SERVER_ERROR },
  { id: 'network', label: 'Network failure', error: new TypeError('Failed to fetch') },
]

const LABEL_GROUPS = [
  ['Category', CATEGORY_LABELS],
  ['Account type', ACCOUNT_TYPE_LABELS],
  ['Kind', KIND_LABELS],
  ['Frequency', FREQUENCY_LABELS],
]

const FALLBACK_EXAMPLES = ['credit_line', 'GIFTS', '']

const NO_ERRORS = { fieldErrors: {}, pageAlert: null }

export default function DevErrors() {
  const [category, setCategory] = useState('food')
  const [errors, setErrors] = useState(NO_ERRORS)
  const [retrying, setRetrying] = useState(false)

  const clearField = (field) =>
    setErrors((prev) => {
      if (!(field in prev.fieldErrors)) return prev
      const { [field]: _removed, ...rest } = prev.fieldErrors
      return { ...prev, fieldErrors: rest }
    })

  function retry() {
    setRetrying(true)
    // Pretend the second attempt succeeds.
    setTimeout(() => {
      setRetrying(false)
      setErrors((prev) => ({ ...prev, pageAlert: null }))
    }, 600)
  }

  return (
    <section className="dashboard" aria-labelledby="dev-errors-title">
      <h2 id="dev-errors-title">Errors and labels demo</h2>

      <PageAlert
        alert={errors.pageAlert}
        onRetry={retry}
        retrying={retrying}
        onDismiss={() => setErrors((prev) => ({ ...prev, pageAlert: null }))}
      />

      <div className="card">
        <h3>Simulate an API failure</h3>
        <div className="button-row button-row-start">
          {SCENARIOS.map((scenario) => (
            <button
              key={scenario.id}
              type="button"
              className="button button-secondary button-small"
              onClick={() => setErrors(mapApiError(scenario.error))}
            >
              {scenario.label}
            </button>
          ))}
          <button type="button" className="button button-small" onClick={() => setErrors(NO_ERRORS)}>
            Clear
          </button>
        </div>

        <form className="form-grid demo-form" noValidate onSubmit={(event) => event.preventDefault()}>
          <MoneyInput
            label="Amount"
            required
            error={errors.fieldErrors.amount ?? null}
            onChange={() => clearField('amount')}
          />
          <SelectField
            label="Category"
            value={category}
            options={toOptions(CATEGORY_LABELS)}
            error={errors.fieldErrors.category ?? null}
            onChange={(value) => {
              setCategory(value)
              clearField('category')
            }}
          />
        </form>
        <p>
          Selected: <code>"{category}"</code> → {categoryLabel(category)}
        </p>

        <h4>mapApiError result</h4>
        <pre className="code-block">{JSON.stringify(errors, null, 2)}</pre>
      </div>

      <div className="card">
        <h3>Enum labels</h3>
        <div className="table-scroll" role="region" aria-label="Enum labels" tabIndex={0}>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Enum</th>
                <th scope="col">API value</th>
                <th scope="col">Label</th>
              </tr>
            </thead>
            <tbody>
              {LABEL_GROUPS.flatMap(([name, labels]) =>
                Object.entries(labels).map(([value, label]) => (
                  <tr key={`${name}-${value}`}>
                    <td>{name}</td>
                    <td>
                      <code>"{value}"</code>
                    </td>
                    <td>{label}</td>
                  </tr>
                )),
              )}
              {FALLBACK_EXAMPLES.map((value) => (
                <tr key={`fallback-${value}`}>
                  <td>Category (unknown)</td>
                  <td>
                    <code>"{value}"</code>
                  </td>
                  <td>{categoryLabel(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
