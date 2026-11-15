import { useRef, useState } from 'react'
import { confirmImport, csvFileError, importCanConfirm, MAX_CSV_SIZE, previewImport } from '../../api/optional.js'

export default function ImportTools({ accounts, onChanged }) {
  const [accountId, setAccountId] = useState('')
  const [csvText, setCsvText] = useState('')
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const lock = useRef(false)

  function clearPreview() { setPreview(null); setNotice(''); setError('') }

  async function run(action) {
    if (lock.current) return
    lock.current = true
    setBusy(true)
    setError('')
    try { await action() } catch (failure) { setError(failure.message) } finally {
      lock.current = false
      setBusy(false)
    }
  }

  async function loadFile(event) {
    const file = event.target.files?.[0]
    if (!file) return
    clearPreview()
    const invalid = csvFileError(file)
    if (invalid) { setError(invalid); return }
    await run(async () => {
      const text = await file.text()
      setCsvText(text)
    })
  }

  async function showPreview() {
    clearPreview()
    await run(async () => {
      const result = await previewImport(accountId, csvText)
      setPreview({ ...result, accountId, csvText })
    })
  }

  async function confirm() {
    await run(async () => {
      const result = await confirmImport(preview, accountId, csvText)
      setNotice(`Imported ${result.accepted.length} transaction(s); skipped ${result.errors.length} invalid row(s).${result.warnings?.length ? ' ' + result.warnings.map((w) => w.message).join('; ') : ''}`)
      setPreview(null)
      onChanged()
    })
  }

  return (
    <section className="card optional-tool" aria-labelledby="import-title" aria-busy={busy}>
      <h3 id="import-title">Bank CSV import</h3>
      <p>Use date, amount and category columns, with optional note and currency. Negative amounts are expenses; positive amounts are income. Dates use YYYY-MM-DD.</p>
      <p className="field-hint">Preview first. Only valid rows are saved. Importing the same file again creates duplicates. Row numbers identify the ending line of each CSV record.</p>
      <fieldset disabled={busy}>
        <legend className="sr-only">Import settings</legend>
        <div className="field">
          <label htmlFor="import-account">Import into account</label>
          <select id="import-account" value={accountId} onChange={(e) => { clearPreview(); setAccountId(e.target.value) }}>
            <option value="">Choose an account</option>
            {accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="import-file">CSV file (UTF-8, up to 1 MB)</label>
          <input id="import-file" type="file" accept=".csv,text/csv" onChange={loadFile} />
        </div>
        <div className="field">
          <label htmlFor="import-csv">CSV contents</label>
          <textarea id="import-csv" rows={7} maxLength={MAX_CSV_SIZE} value={csvText}
            placeholder={'date,amount,category,note\n2026-11-15,-12.50,food,Lunch'}
            onChange={(e) => { clearPreview(); setCsvText(e.target.value) }} />
        </div>
        <div className="button-row">
          <button className="button" type="button" disabled={!accountId || !csvText.trim()} onClick={showPreview}>Preview CSV</button>
          <button className="button" type="button" disabled={!importCanConfirm(preview, accountId, csvText)} onClick={confirm}>Confirm valid rows</button>
        </div>
      </fieldset>
      {busy && <p role="status">Processing CSV...</p>}
      {error && <p role="alert" className="field-error">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {preview && <>
        <p role="status">{preview.accepted.length} valid row(s), {preview.errors.length} rejected row(s). Preview has not saved anything.</p>
        <div className="table-scroll"><table className="data-table">
          <caption>Valid rows to import (first 100 shown)</caption>
          <thead><tr><th scope="col">Row</th><th scope="col">Date</th><th scope="col">Type</th><th scope="col">Amount</th><th scope="col">Note</th></tr></thead>
          <tbody>{preview.accepted.slice(0, 100).map(({ row_number: row, transaction: tx }) => <tr key={row}>
            <td>{row}</td><td>{tx.date}</td><td>{tx.kind}</td><td>{tx.amount} {tx.currency}</td><td>{tx.note}</td>
          </tr>)}</tbody>
        </table></div>
        {preview.errors.length > 0 && <div className="table-scroll"><table className="data-table">
          <caption>Rejected rows (first 100 shown)</caption>
          <thead><tr><th scope="col">Row</th><th scope="col">Reason</th></tr></thead>
          <tbody>{preview.errors.slice(0, 100).map((issue) => <tr key={issue.row_number}><td>{issue.row_number}</td><td>{issue.reason}</td></tr>)}</tbody>
        </table></div>}
      </>}
    </section>
  )
}
