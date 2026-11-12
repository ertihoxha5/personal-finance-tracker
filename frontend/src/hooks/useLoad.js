import { useCallback, useEffect, useState } from 'react'

// Runs loader() whenever `id` changes or reload() is called.
// Returns { status, data, error, reload } where status is 'loading' | 'success' | 'error'.
// While reloading the same id, data keeps the previous response so lists don't flash empty.
// When the id changes, data is cleared, so one item's data never shows under another.
export function useLoad(loader, id) {
  const [state, setState] = useState({ id, status: 'loading', data: null, error: null })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    // `cancelled` drops the answer of a superseded request, so rapid switching can never
    // let a slow response for an old id overwrite the current one.
    let cancelled = false
    setState((prev) => ({
      id,
      status: 'loading',
      data: prev.id === id ? prev.data : null,
      error: null,
    }))

    loader().then(
      (data) => {
        if (!cancelled) setState({ id, status: 'success', data, error: null })
      },
      (error) => {
        if (!cancelled) {
          setState((prev) => ({ id, status: 'error', data: prev.id === id ? prev.data : null, error }))
        }
      },
    )

    return () => {
      cancelled = true
    }
    // loader is rebuilt on every render by the caller; id and attempt are what should retrigger it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, attempt])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])

  // For the one render between an id change and the effect above, never hand out data
  // that belongs to the previous id.
  if (state.id !== id) return { status: 'loading', data: null, error: null, reload }
  return { status: state.status, data: state.data, error: state.error, reload }
}
