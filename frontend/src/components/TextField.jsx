import { useId } from 'react'

// Labelled text input with an inline error linked through aria-describedby (#12).
// Same shape as SelectField: the form owns the value and passes `error` (a local
// validation message or a server message from mapApiError).
export default function TextField({ label, name, value, onChange, error = null, hint, id, maxLength, required }) {
  const generatedId = useId()
  const inputId = id ?? generatedId
  const hintId = `${inputId}-hint`
  const errorId = `${inputId}-error`
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(' ')

  return (
    <div className="field">
      <label htmlFor={inputId}>{label}</label>
      <input
        id={inputId}
        name={name}
        type="text"
        value={value}
        maxLength={maxLength}
        required={required}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={error !== null}
        aria-describedby={describedBy || undefined}
      />
      {hint && (
        <p id={hintId} className="field-hint">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="field-error">
          {error}
        </p>
      )}
    </div>
  )
}
