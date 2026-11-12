import { useId } from 'react'

// Labelled <select> with an inline error linked through aria-describedby (#10).
// `options` is [{ value, label }], e.g. toOptions(CATEGORY_LABELS) from lib/labels.js.
export default function SelectField({ label, value, onChange, options, error = null, id, name }) {
  const generatedId = useId()
  const selectId = id ?? generatedId
  const errorId = `${selectId}-error`

  return (
    <div className="field">
      <label htmlFor={selectId}>{label}</label>
      <select
        id={selectId}
        name={name}
        className="select-input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={error !== null}
        aria-describedby={error ? errorId : undefined}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error && (
        <p id={errorId} className="field-error">
          {error}
        </p>
      )}
    </div>
  )
}
