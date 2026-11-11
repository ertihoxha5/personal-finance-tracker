import { useCallback, useEffect, useState } from 'react'
import { fetchDashboard } from '../api/dashboard.js'

// Returns { status, data, error, retry } where status is
// 'loading' | 'success' | 'empty' | 'error'. While reloading, data keeps the
// previous response so controls such as the month picker stay populated.
export function useDashboard(month) {
  const [state, setState] = useState({ status: 'loading', data: null, error: null })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    setState((prev) => ({ status: 'loading', data: prev.data, error: null }))

    fetchDashboard(month).then(
      (data) => {
        if (cancelled) return
        const empty = data.recentTransactions.length === 0 && data.categories.length === 0
        setState({ status: empty ? 'empty' : 'success', data, error: null })
      },
      (error) => {
        if (!cancelled) setState((prev) => ({ status: 'error', data: prev.data, error }))
      },
    )

    return () => {
      cancelled = true
    }
  }, [month, attempt])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])

  return { ...state, retry }
}
