import { useRef, useState } from 'react'
import { downloadBlob, requestChart } from '../../api/optional.js'
import { todayISO } from '../../lib/transactions.js'

export default function ChartTools() {
  const today = todayISO()
  const [start, setStart] = useState(`${today.slice(0, 7)}-01`)
  const [end, setEnd] = useState(today)
  const [month, setMonth] = useState(today.slice(0, 7))
  const [months, setMonths] = useState('6')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const lock = useRef(false)

  async function download(event, kind) {
    event.preventDefault()
    if (lock.current) return
    lock.current = true
    setBusy(true); setError(''); setNotice('')
    try {
      const filters = kind === 'categories' ? { start, end } : { end: month, months }
      const blob = await requestChart(kind, filters)
      const filename = kind === 'categories' ? `categories-${start}-${end}.png` : `trend-${month}-${months}-months.png`
      downloadBlob(blob, filename)
      setNotice(`Download started: ${filename}`)
    } catch (failure) { setError(failure.message) } finally { lock.current = false; setBusy(false) }
  }

  return (
    <section className="card optional-tool" aria-labelledby="chart-title" aria-busy={busy}>
      <h3 id="chart-title">PNG charts</h3>
      <p>Download a category pie chart or monthly income, expenses and net. Values come from the same reports as the core screens.</p>
      <form onSubmit={(event) => download(event, 'categories')}>
        <fieldset disabled={busy}>
          <legend>Category spending (inclusive dates)</legend>
          <div className="form-grid">
            <div className="field"><label htmlFor="chart-start">Start date</label><input id="chart-start" type="date" required value={start} onChange={(e) => setStart(e.target.value)} /></div>
            <div className="field"><label htmlFor="chart-end">End date</label><input id="chart-end" type="date" required min={start} value={end} onChange={(e) => setEnd(e.target.value)} /></div>
          </div>
          <button className="button" type="submit">Download category PNG</button>
        </fieldset>
      </form>
      <form onSubmit={(event) => download(event, 'trend')}>
        <fieldset disabled={busy}>
          <legend>Monthly trend</legend>
          <div className="form-grid">
            <div className="field"><label htmlFor="chart-month">Ending month</label><input id="chart-month" type="month" required min="1900-01" max="9998-12" value={month} onChange={(e) => setMonth(e.target.value)} /></div>
            <div className="field"><label htmlFor="chart-months">Number of months</label><input id="chart-months" type="number" required min="1" max="120" step="1" value={months} onChange={(e) => setMonths(e.target.value)} /></div>
          </div>
          <button className="button" type="submit">Download trend PNG</button>
        </fieldset>
      </form>
      {busy && <p role="status">Preparing PNG...</p>}
      {error && <p role="alert" className="field-error">{error}</p>}
      {notice && <p role="status">{notice}</p>}
    </section>
  )
}
