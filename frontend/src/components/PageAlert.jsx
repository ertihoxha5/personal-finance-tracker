import { useEffect, useRef } from 'react'

// Recoverable page-level error (#10): network failures, server errors and domain
// errors that do not belong to one input. Pass the `pageAlert` from mapApiError.
// role="alert" makes screen readers announce it; focus moves to it so keyboard
// users land on the retry button. Retry shows only when the failure may succeed again.
export default function PageAlert({ alert, onRetry, onDismiss, retrying = false }) {
  const ref = useRef(null)

  useEffect(() => {
    if (alert) ref.current?.focus()
  }, [alert])

  if (!alert) return null

  return (
    <div ref={ref} className="page-alert" role="alert" tabIndex={-1}>
      <p className="page-alert-message">{alert.message}</p>
      <div className="page-alert-actions">
        {alert.retryable && onRetry && (
          <button type="button" className="button button-small" onClick={onRetry} disabled={retrying}>
            {retrying ? 'Retrying…' : 'Try again'}
          </button>
        )}
        {onDismiss && (
          <button type="button" className="button button-secondary button-small" onClick={onDismiss}>
            Dismiss
          </button>
        )}
      </div>
    </div>
  )
}
