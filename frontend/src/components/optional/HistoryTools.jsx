import { useRef, useState } from 'react'
import { historyAction, readHistory, startHistory } from '../../api/optional.js'
import { searchTransactions } from '../../api/transactions.js'
import { emptyFilters } from '../../lib/transactionFilters.js'
import { useLoad } from '../../hooks/useLoad.js'
import TransactionForm from '../transactions/TransactionForm.jsx'
import TransferForm from '../accounts/TransferForm.jsx'
import ConfirmDialog from '../accounts/ConfirmDialog.jsx'

export default function HistoryTools({ accounts, onChanged }) {
  const [session, setSession] = useState(null)
  const [version, setVersion] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [transfer, setTransfer] = useState(false)
  const [pendingDelete, setPendingDelete] = useState(null)
  const lock = useRef(false)
  const rows = useLoad(() => session ? searchTransactions(emptyFilters()) : Promise.resolve([]), `${Boolean(session)}|${version}`)

  async function run(action) {
    if (lock.current) return { ok: false, error: new Error('Wait for the current operation.') }
    lock.current = true; setBusy(true); setError(''); setNotice('')
    try {
      await action()
      return { ok: true }
    } catch (failure) {
      setError(failure.message)
      return { ok: false, error: failure }
    } finally { lock.current = false; setBusy(false) }
  }

  async function begin() {
    await run(async () => { setSession(await startHistory()); setVersion((value) => value + 1) })
  }

  async function refresh() {
    await run(async () => {
      const next = await readHistory(session.token)
      setSession(next)
      setVersion((value) => value + 1)
      onChanged()
      setNotice(next.reset ? 'Data changed outside this session. History was cleared.' : 'History refreshed.')
    })
  }

  async function act(body) {
    return run(async () => {
      const next = await historyAction(session.token, body)
      setSession(next)
      setVersion((value) => value + 1)
      setPendingDelete(null)
      onChanged()
      setNotice(`Saved ${body.action}.${next.warnings?.length ? ' ' + next.warnings.map((warning) => warning.message).join('; ') : ''}`)
    })
  }

  async function add(transaction) {
    const outcome = await act({ action: 'add', transaction })
    if (!outcome.ok) throw outcome.error
  }

  async function move(values) {
    const outcome = await act({ action: 'transfer', transfer: {
      from_account_id: values.fromAccountId, to_account_id: values.toAccountId,
      amount: values.amount, date: values.date, note: values.note,
    } })
    if (outcome.ok) setTransfer(false)
    return outcome
  }

  return (
    <section className="card optional-tool" aria-labelledby="history-title" aria-busy={busy}>
      <h3 id="history-title">Undo and redo workspace</h3>
      <p>Only actions made here belong to this history. Changes on other screens clear it. History ends when the server restarts or after one hour of inactivity.</p>
      <div className="button-row">
        <button className="button" type="button" onClick={begin} disabled={busy}>Start new history</button>
        {session && <>
          <button className="button button-secondary" type="button" onClick={refresh} disabled={busy}>Refresh history</button>
          <button className="button" type="button" disabled={busy || !session.can_undo} onClick={() => act({ action: 'undo' })}>Undo</button>
          <button className="button" type="button" disabled={busy || !session.can_redo} onClick={() => act({ action: 'redo' })}>Redo</button>
        </>}
      </div>
      {busy && <p role="status">Saving tools operation...</p>}
      {error && <p className="field-error" role="alert">{error} Refresh history or start a new session to continue.</p>}
      {notice && <p role="status">{notice}</p>}
      {session && <fieldset disabled={busy}>
        <legend className="sr-only">History operations</legend>
        {accounts.length > 0 ? <TransactionForm accounts={accounts} onSubmit={add} title="Add an undoable transaction" /> : <p>Add an account on Accounts first.</p>}
        {accounts.length > 1 && <button className="button button-secondary" type="button" onClick={() => setTransfer(true)}>New undoable transfer</button>}
        {transfer && <TransferForm accounts={accounts} onSubmit={move} onCancel={() => setTransfer(false)} busy={busy} />}
        {rows.status === 'error' && <p role="alert">{rows.error.message} <button type="button" onClick={rows.reload}>Retry transactions</button></p>}
        {rows.status === 'loading' && <p role="status">Loading transactions...</p>}
        {rows.status === 'success' && <div className="table-scroll"><table className="data-table">
          <caption>Transactions available for undoable deletion (first 100 shown)</caption>
          <thead><tr><th scope="col">Date</th><th scope="col">Account</th><th scope="col">Type</th><th scope="col">Amount</th><th scope="col">Note</th><th scope="col">Action</th></tr></thead>
          <tbody>{rows.data.slice(0, 100).map((tx) => <tr key={tx.id}>
            <td>{tx.date}</td><td>{accounts.find((a) => a.id === tx.account_id)?.name ?? tx.account_id}</td><td>{tx.kind}</td><td>{tx.amount} {tx.currency}</td><td>{tx.note}</td>
            <td><button className="button button-secondary" type="button" aria-label={`Delete transaction ${tx.id}`} onClick={() => setPendingDelete(tx)}>Delete</button></td>
          </tr>)}</tbody>
        </table>{rows.data.length === 0 && <p>No transactions yet.</p>}</div>}
      </fieldset>}
      {pendingDelete && <ConfirmDialog title="Delete transaction?" confirmLabel="Delete transaction" busy={busy} error={error}
        onCancel={() => { if (!busy) setPendingDelete(null) }}
        onConfirm={() => act({ action: 'delete', account_id: pendingDelete.account_id, transaction_id: pendingDelete.id })}>
        <p>{pendingDelete.note || pendingDelete.category}: {pendingDelete.amount} {pendingDelete.currency}. {pendingDelete.kind === 'transfer' ? 'Both linked transfer rows will be deleted.' : ''} You can undo this through this workspace.</p>
      </ConfirmDialog>}
    </section>
  )
}
