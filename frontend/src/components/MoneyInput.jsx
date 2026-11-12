import { useId, useState } from 'react'
import { parseMoneyInput } from '../lib/money.js'

// Text input for EUR amounts. A text field with inputMode="decimal" (not
// type="number") so "12,50" is accepted and browsers don't alter the value.
// onChange receives the normalised string ("12.50") or null while the text is
// empty or invalid, plus the raw text as a second argument for form validation (#12).
// `name` lets a form focus the input by name. Errors appear after the field loses focus. `error` is a message
// from the server (mapApiError's fieldErrors) and shows at once, over local errors.
export default function MoneyInput({
  label,
  defaultValue = '',
  onChange,
  required = false,
  allowNegative = false,
  hint,
  id,
  name,
  error: serverError = null,
}) {
  const generatedId = useId()
  const inputId = id ?? generatedId
  const hintId = `${inputId}-hint`
  const errorId = `${inputId}-error`

  const [text, setText] = useState(defaultValue)
  const [touched, setTouched] = useState(false)

  const parsed = parseMoneyInput(text, { allowNegative })
  const localError = parsed.error ?? (required && parsed.value === null ? 'Enter an amount.' : null)
  const error = serverError ?? (touched ? localError : null)
  const showError = error !== null

  function handleChange(event) {
    const next = event.target.value
    setText(next)
    onChange?.(parseMoneyInput(next, { allowNegative }).value, next)
  }

  function handleBlur() {
    setTouched(true)
    if (parsed.value !== null) setText(parsed.value)
  }

  const describedBy = [hint ? hintId : null, showError ? errorId : null].filter(Boolean).join(' ')

  return (
    <div className="field">
      <label htmlFor={inputId}>{label}</label>
      <div className="money-input">
        <span className="money-input-prefix" aria-hidden="true">
          €
        </span>
        <input
          id={inputId}
          name={name}
          type="text"
          inputMode={allowNegative ? 'text' : 'decimal'}
          autoComplete="off"
          value={text}
          onChange={handleChange}
          onBlur={handleBlur}
          required={required}
          aria-invalid={showError}
          aria-describedby={describedBy || undefined}
        />
      </div>
      {hint && (
        <p id={hintId} className="field-hint">
          {hint}
        </p>
      )}
      {showError && (
        <p id={errorId} className="field-error">
          {error}
        </p>
      )}
    </div>
  )
}
