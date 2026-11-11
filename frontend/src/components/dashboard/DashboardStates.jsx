import { formatMonth } from '../../lib/format.js'

export function DashboardLoading() {
  return (
    <div className="state-loading" role="status">
      <span className="sr-only">Loading dashboard…</span>
      <div className="skeleton-row" aria-hidden="true">
        <div className="card skeleton skeleton-card" />
        <div className="card skeleton skeleton-card" />
        <div className="card skeleton skeleton-card" />
      </div>
      <div className="card skeleton skeleton-block" aria-hidden="true" />
    </div>
  )
}

export function DashboardEmpty({ month }) {
  return (
    <div className="card state-message" role="status">
      <h3>No transactions in {formatMonth(month)}</h3>
      <p>Once transactions are added for this month, your summary and charts will show here.</p>
    </div>
  )
}

export function DashboardError({ message, onRetry }) {
  return (
    <div className="card state-message state-error" role="alert">
      <h3>Something went wrong</h3>
      <p>{message}</p>
      <button type="button" className="button" onClick={onRetry}>
        Try again
      </button>
    </div>
  )
}
