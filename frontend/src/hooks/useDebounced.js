import { useEffect, useState } from 'react'

// Returns `value` after it has stopped changing for `delay` ms, so typing in a search box
// sends one request instead of one per keystroke.
export function useDebounced(value, delay = 250) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}
