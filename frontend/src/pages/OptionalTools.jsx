import { fetchOptionalFeatures, optionalEnabled } from '../api/optional.js'
import { listAccounts } from '../api/accounts.js'
import ChartTools from '../components/optional/ChartTools.jsx'
import HistoryTools from '../components/optional/HistoryTools.jsx'
import ImportTools from '../components/optional/ImportTools.jsx'
import { useLoad } from '../hooks/useLoad.js'
import './OptionalTools.css'

function EnabledTools({ features }) {
  const accounts = useLoad(listAccounts, 'optional-accounts')
  return <>
    {accounts.status === 'error' && <p role="alert">{accounts.error.message} <button className="button" type="button" onClick={accounts.reload}>Retry accounts</button></p>}
    {accounts.status === 'loading' && <p role="status">Loading accounts...</p>}
    {features.undo && accounts.data && <HistoryTools accounts={accounts.data} onChanged={accounts.reload} />}
    {features.import && accounts.data && <ImportTools accounts={accounts.data} onChanged={accounts.reload} />}
    {features.charts && <ChartTools />}
  </>
}

export default function OptionalTools() {
  const features = useLoad(fetchOptionalFeatures, 'optional-features')
  return <section className="optional-tools" aria-labelledby="tools-title">
    <h2 id="tools-title">Optional tools</h2>
    <p>Extra tools for imports, undoable changes and PNG charts. The normal Dashboard, Transactions, Budgets and Accounts screens work independently.</p>
    {features.status === 'loading' && <p role="status">Checking enabled tools...</p>}
    {features.status === 'error' && <div role="alert"><p>{features.error.message}</p><button className="button" type="button" onClick={features.reload}>Retry tools</button></div>}
    {features.status === 'success' && (optionalEnabled(features.data)
      ? <EnabledTools features={features.data} />
      : <p role="status">Optional tools are disabled. Your core screens are available as usual.</p>)}
  </section>
}
