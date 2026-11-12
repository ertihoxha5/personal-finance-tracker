// Shows whether the last change reached the database (#18): saving, saved or not saved.
// `save` is { state: 'idle' | 'saving' | 'saved' | 'failed', message? }. "Saved" is only
// set after the API answered success, and the API answers only after SQLite committed.
export default function SaveStatus({ save }) {
  return (
    <p className={`save-status save-status-${save.state}`} role="status" aria-live="polite">
      {save.state === 'saving' && 'Saving…'}
      {save.state === 'saved' && 'All changes saved'}
      {save.state === 'failed' && (
        <>
          <strong>Not saved.</strong> {save.message} Nothing was changed.
        </>
      )}
    </p>
  )
}
