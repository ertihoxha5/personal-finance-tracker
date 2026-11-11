import { useEffect, useRef } from 'react'

// Modal confirmation built on <dialog>, so focus is trapped and Escape cancels.
// `error` shows a failed attempt inside the dialog, so the user can retry or cancel.
export default function ConfirmDialog({ title, children, confirmLabel, busy, error, onConfirm, onCancel }) {
  const ref = useRef(null)

  useEffect(() => {
    const dialog = ref.current
    if (dialog && !dialog.open) dialog.showModal()
  }, [])

  return (
    <dialog ref={ref} className="confirm-dialog" aria-labelledby="confirm-title" onCancel={onCancel}>
      <h3 id="confirm-title">{title}</h3>
      <div>{children}</div>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      <div className="button-row">
        <button type="button" className="button button-secondary" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button type="button" className="button button-danger" onClick={onConfirm} disabled={busy}>
          {busy ? 'Deleting…' : confirmLabel}
        </button>
      </div>
    </dialog>
  )
}
