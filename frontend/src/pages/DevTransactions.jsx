import { useState } from 'react'
import { fromApi } from '../api/transactions.js'
import TransactionForm from '../components/transactions/TransactionForm.jsx'
import TransactionRows from '../components/transactions/TransactionRows.jsx'
import { FIELD_ERROR, PAGE_ERROR } from '../fixtures/apiErrors.js'
import { FILTER_ACCOUNTS, DEMO_TRANSACTIONS } from '../fixtures/transactions.js'

// Development-only demo for #14/#17: the shared income/expense form with fixture
// responses, and rows of all three kinds, both transfer directions and one unknown kind.
// Fixture DTOs and the echoed request body go through fromApi, as live API data will (#19).
// Registered in App.jsx only in DEV.

const SCENARIOS = [
  { id: 'success', label: 'Success', delay: 500 },
  { id: 'field', label: 'Field error (amount)', delay: 500, error: FIELD_ERROR },
  { id: 'account', label: 'Field error (account)', delay: 500, error: { code: 'account_not_found', message: 'that account was closed; choose another', field: 'account_id' } },
  { id: 'page', label: 'Page error', delay: 500, error: PAGE_ERROR },
]

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const accountName = (id) => FILTER_ACCOUNTS.find((account) => account.id === id)?.name ?? `Account ${id}`

export default function DevTransactions() {
  const [scenarioId, setScenarioId] = useState('success')
  const [rows, setRows] = useState(() => DEMO_TRANSACTIONS.map(fromApi))
  const [lastBody, setLastBody] = useState(null)

  async function submit(dto) {
    const scenario = SCENARIOS.find((s) => s.id === scenarioId)
    setLastBody(dto)
    await wait(scenario.delay)
    if (scenario.error) throw scenario.error
    setRows((prev) => [...prev, fromApi({ ...dto, id: Math.max(...prev.map((r) => r.id)) + 1 })])
  }

  return (
    <section className="dashboard" aria-labelledby="dev-transactions-title">
      <h2 id="dev-transactions-title">Transactions demo</h2>

      <div className="card">
        <fieldset className="demo-scenarios">
          <legend>Fixture server response</legend>
          {SCENARIOS.map((scenario) => (
            <label key={scenario.id} className="radio-option">
              <input
                type="radio"
                name="scenario"
                value={scenario.id}
                checked={scenarioId === scenario.id}
                onChange={() => setScenarioId(scenario.id)}
              />
              {scenario.label}
            </label>
          ))}
        </fieldset>
      </div>

      <TransactionForm accounts={FILTER_ACCOUNTS} defaultAccountId={1} onSubmit={submit} />

      <div className="card">
        <h3>Last request body</h3>
        <pre className="code-block">{lastBody ? JSON.stringify(lastBody, null, 2) : 'Nothing sent yet.'}</pre>
      </div>

      <div className="card">
        <h3>Rows</h3>
        <TransactionRows transactions={rows} accountName={accountName} caption="Demo transactions of every kind" />
      </div>
    </section>
  )
}
