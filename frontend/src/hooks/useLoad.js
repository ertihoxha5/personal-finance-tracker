import { useCallback, useEffect, useState } from 'react'

// Runs loader() whenever `key` changes or reload() is called.
// Returns { status, data, error, reload } where status is 'loading' | 'success' | 'error'.
// While reloading, data keeps the previous response so lists don't flash empty.
export function useLoad(loader, key) {
  const [state, setState] = useState({ status: 'loading', data: null, error: null })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    setState((prev) => ({ status: 'loading', data: prev.data, error: null }))

    loader().then(
      (data) => {
        if (!cancelled) setState({ status: 'success', data, error: null })
      },
      (error) => {
        if (!cancelled) setState((prev) => ({ status: 'error', data: prev.data, error }))
      },
    )

    return () => {
      cancelled = true
    }
    // loader is rebuilt on every render by the caller; key and attempt are what should retrigger it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])

  return { ...state, reload }
}
