import { useState } from 'react'
import MoneyInput from '../components/MoneyInput.jsx'
import PageAlert from '../components/PageAlert.jsx'
import SelectField from '../components/SelectField.jsx'
import TextField from '../components/TextField.jsx'
import { FIELD_ERROR, PAGE_ERROR } from '../fixtures/apiErrors.js'
import useFormValidation from '../hooks/useFormValidation.js'
import { CATEGORY_LABELS, toOptions } from '../lib/labels.js'
import { parseMoneyInput } from '../lib/money.js'
import { positiveDecimal, required } from '../lib/validation.js'

// Development-only demo for #12: client validation before submit, server errors beside
// their fields, input kept on error and no double submission. The "server" is a fixture
// that answers after a delay. The real transaction form is #14.

const SCENARIOS = [
  { id: 'success', label: 'Success', delay: 600 },
  { id: 'field', label: 'Field error (amount)', delay: 600, error: FIELD_ERROR },
  { id: 'page', label: 'Page error (not found)', delay: 600, error: PAGE_ERROR },
  { id: 'slow', label: 'Slow success (3 s)', delay: 3000 },
]

const CATEGORY_OPTIONS = [{ value: '', label: 'Choose a category…' }, ...toOptions(CATEGORY_LABELS)]

const INITIAL_VALUES = { description: '', amount: '', category: '' }

const RULES = {
  description: required,
  amount: positiveDecimal,
  category: (value) => required(value, 'Choose a category.'),
}

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

export default function DevValidation() {
  const [scenarioId, setScenarioId] = useState('success')
  const [requests, setRequests] = useState([])
  const [saved, setSaved] = useState(null)

  const form = useFormValidation({
    initialValues: INITIAL_VALUES,
    rules: RULES,
    onSubmit: async (values) => {
      const scenario = SCENARIOS.find((s) => s.id === scenarioId)
      // Amounts travel as normalised decimal strings, exactly as the API expects.
      const payload = { ...values, description: values.description.trim(), amount: parseMoneyInput(values.amount).value }
      setSaved(null)
      setRequests((prev) => [...prev, payload])
      await wait(scenario.delay)
      if (scenario.error) throw scenario.error
      setSaved(payload)
      form.reset()
    },
  })

  return (
    <section className="dashboard" aria-labelledby="dev-validation-title">
      <h2 id="dev-validation-title">Form validation demo</h2>

      <PageAlert alert={form.pageAlert} onDismiss={form.dismissAlert} />

      <div className="card">
        <fieldset className="demo-scenarios">
          <legend>Fixture server response</legend>
          {SCENARIOS.map((scenario) => (
            <label key={scenario.id} className="radio-option">
              <input
                type="radio"
                name="scenario"
                value={scenario.id}
                checked={scenarioId === scenario.id}
                onChange={() => setScenarioId(scenario.id)}
              />
              {scenario.label}
            </label>
          ))}
        </fieldset>

        <form ref={form.formRef} className="form-grid demo-form" noValidate onSubmit={form.handleSubmit}>
          <TextField
            label="Description"
            name="description"
            value={form.values.description}
            maxLength={120}
            required
            onChange={(value) => form.setValue('description', value)}
            error={form.errors.description ?? null}
          />
          <MoneyInput
            key={form.generation}
            label="Amount"
            name="amount"
            required
            hint="Greater than zero, e.g. 12,50."
            onChange={(_value, text) => form.setValue('amount', text)}
            error={form.errors.amount ?? null}
          />
          <SelectField
            label="Category"
            name="category"
            value={form.values.category}
            options={CATEGORY_OPTIONS}
            onChange={(value) => form.setValue('category', value)}
            error={form.errors.category ?? null}
          />
          <div className="button-row button-row-start">
            <button type="submit" className="button" disabled={form.submitting} aria-busy={form.submitting}>
              {form.submitting ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>

        {saved && (
          <p role="status">
            Saved <code>{JSON.stringify(saved)}</code>
          </p>
        )}

        <h4>Requests sent: {requests.length}</h4>
        <pre className="code-block">{JSON.stringify(requests, null, 2)}</pre>
      </div>
    </section>
  )
}
