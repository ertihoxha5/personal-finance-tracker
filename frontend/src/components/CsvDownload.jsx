import { useEffect, useId, useRef, useState } from 'react'
import { EXPORT_FORMATS, filenameError, requestExport } from '../api/exports.js'
import './CsvDownload.css'

export default function CsvDownload({ defaultFilename, buildExport, disabled = false, label = 'Download' }) {
  const id = useId()
  const [filename, setFilename] = useState(defaultFilename)
  const [format, setFormat] = useState('csv')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState('')
  const request = useRef(null)

  useEffect(() => () => request.current?.abort(), [])

  function changeFilename(event) {
    setFilename(event.target.value)
    setError(null)
    setNotice('')
  }

  async function download() {
    if (request.current || disabled) return
    const invalid = filenameError(filename, format)
    setError(invalid)
    setNotice('')
    if (invalid) return
    const controller = new AbortController()
    request.current = controller
    setPending(true)
    try {
      const payload = { ...buildExport(), filename }
      const blob = await requestExport(payload, format, { signal: controller.signal })
      if (controller.signal.aborted) return
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = payload.filename
      document.body.append(link)
      try {
        link.click()
      } finally {
        link.remove()
        setTimeout(() => URL.revokeObjectURL(url), 1000)
      }
      setNotice(`Download started: ${payload.filename}`)
    } catch (failure) {
      if (!controller.signal.aborted) {
        const message = failure instanceof Error ? failure.message : 'The export could not be downloaded.'
        setError(failure instanceof TypeError ? 'Could not reach the API. Start the backend and try again.' : message)
      }
    } finally {
      request.current = null
      setPending(false)
    }
  }

  return (
    <div className="csv-download" aria-busy={pending}>
      <div className="csv-download-controls">
        <div className="field">
          <label htmlFor={`${id}-format`}>Export format</label>
          <select id={`${id}-format`} value={format} disabled={pending || disabled}
            onChange={(event) => {
              const next = event.target.value
              setFormat(next)
              setFilename((previous) => previous.replace(/\.(csv|json|md)$/, '') + `.${next}`)
              setError(null)
              setNotice('')
            }}>
            {Object.entries(EXPORT_FORMATS).map(([value, name]) => <option key={value} value={value}>{name}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor={id}>Export filename</label>
          <input
            id={id}
            value={filename}
            onChange={changeFilename}
            disabled={pending || disabled}
            aria-invalid={Boolean(error && filenameError(filename, format))}
            aria-describedby={error ? `${id}-error` : undefined}
          />
        </div>
        <button type="button" className="button" onClick={download} disabled={pending || disabled}>
          {pending ? 'Preparing download…' : `${label.replace(/ CSV$/, '')} ${EXPORT_FORMATS[format]}`}
        </button>
      </div>
      <p role="status">{pending ? 'Preparing your download…' : notice}</p>
      {error && <p className="field-error" role="alert" id={`${id}-error`}>{error} Use the download button to try again.</p>}
    </div>
  )
}
