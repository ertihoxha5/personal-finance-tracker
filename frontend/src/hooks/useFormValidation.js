import { useCallback, useRef, useState } from 'react'
import { mapApiError } from '../lib/apiErrors.js'
import { validateFields } from '../lib/validation.js'

// Form state, client validation and server errors for one form (#12).
//
//   const form = useFormValidation({ initialValues, rules, onSubmit })
//   <form ref={form.formRef} onSubmit={form.handleSubmit} noValidate>
//
// - Nothing is checked while the user first types. The first submit validates every
//   field; after that each change re-validates, so errors disappear as they are fixed.
// - On a failed check, focus moves to the first invalid field (inputs need `name`).
// - onSubmit(values) is awaited. If it throws, the error goes through mapApiError (#10):
//   errors for a field in `rules` show beside that field, everything else becomes the
//   page alert. Values are never reset on an error, so nothing the user typed is lost.
// - While a request is in flight `submitting` is true (disable the button and set
//   aria-busy), and a ref guard drops further submits: pressing Enter in a field submits
//   the form even when the button is disabled.
export default function useFormValidation({ initialValues, rules, onSubmit }) {
  const [values, setValues] = useState(initialValues)
  const [attempted, setAttempted] = useState(false)
  const [serverErrors, setServerErrors] = useState({})
  const [pageAlert, setPageAlert] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [generation, setGeneration] = useState(0)
  const inFlight = useRef(false)
  const formRef = useRef(null)

  // Local errors are derived from the current values, never stored, so they can't go stale.
  const localErrors = attempted ? validateFields(values, rules) : {}
  const errors = {}
  for (const field of Object.keys(rules)) {
    const message = serverErrors[field] ?? localErrors[field]
    if (message) errors[field] = message
  }

  const setValue = useCallback((field, value) => {
    setValues((prev) => (prev[field] === value ? prev : { ...prev, [field]: value }))
    // The server's message was about the old value; drop it once the user edits.
    setServerErrors((prev) => {
      if (!(field in prev)) return prev
      const { [field]: _old, ...rest } = prev
      return rest
    })
  }, [])

  function focusField(field) {
    const element = formRef.current?.elements.namedItem(field)
    if (element && typeof element.focus === 'function') element.focus()
  }

  async function handleSubmit(event) {
    event?.preventDefault()
    if (inFlight.current) return

    setAttempted(true)
    const invalid = Object.keys(validateFields(values, rules))
    if (invalid.length > 0) {
      focusField(invalid[0])
      return
    }

    inFlight.current = true
    setSubmitting(true)
    setServerErrors({})
    setPageAlert(null)
    try {
      await onSubmit(values)
    } catch (error) {
      const { fieldErrors, pageAlert: alert } = mapApiError(error)
      const known = {}
      let unknownMessage = null
      for (const [field, message] of Object.entries(fieldErrors)) {
        if (field in rules) known[field] = message
        else unknownMessage ??= message
      }
      setServerErrors(known)
      // A field error for an input this form doesn't have would be invisible inline.
      setPageAlert(alert ?? (unknownMessage ? { code: 'field_error', message: unknownMessage, retryable: false } : null))
      const firstField = Object.keys(rules).find((field) => field in known)
      if (firstField) focusField(firstField)
    } finally {
      inFlight.current = false
      setSubmitting(false)
    }
  }

  // Clear the form after a success. `generation` changes so uncontrolled inputs such as
  // MoneyInput can be remounted with key={generation}.
  const reset = useCallback(() => {
    setValues(initialValues)
    setAttempted(false)
    setServerErrors({})
    setPageAlert(null)
    setGeneration((n) => n + 1)
  }, [initialValues])

  return {
    values,
    setValue,
    errors,
    pageAlert,
    dismissAlert: () => setPageAlert(null),
    submitting,
    handleSubmit,
    formRef,
    reset,
    generation,
  }
}
