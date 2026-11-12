import { formatEUR } from '../lib/money.js'

// Total net worth exactly as the API sends it; React does no arithmetic on money.
// `net` is the { status, data, error, reload } object from useLoad(getNetWorth, ...).
export default function NetWorthCard({ net }) {
  const stale = net.status === 'error' && net.data
  return (
    <div className="card summary-card net-worth" aria-labelledby="net-worth-label">
      <h3 id="net-worth-label" className="summary-label">
        Net worth
      </h3>
      {net.status === 'error' && !net.data ? (
        <p className="field-error" role="alert">
          {net.error?.message}{' '}
          <button type="button" className="link-button" onClick={net.reload}>
            Try again
          </button>
        </p>
      ) : !net.data ? (
        <p className="summary-value" role="status">
          <span className="sr-only">Loading net worth…</span>
          <span aria-hidden="true">…</span>
        </p>
      ) : (
        <>
          <p className={`summary-value ${net.data.netWorth.startsWith('-') ? 'amount-expense' : ''}`}>
            {formatEUR(net.data.netWorth)}
          </p>
          <p className="summary-meta">
            Across {net.data.accountCount} account{net.data.accountCount === 1 ? '' : 's'}
          </p>
          {stale && (
            <p className="field-error" role="alert">
              May be out of date: {net.error?.message}{' '}
              <button type="button" className="link-button" onClick={net.reload}>
                Try again
              </button>
            </p>
          )}
        </>
      )}
    </div>
  )
}
