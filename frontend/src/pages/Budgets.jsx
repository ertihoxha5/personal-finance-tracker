import { useState } from 'react'
import { listAccounts } from '../api/accounts.js'
import { deleteBudget, listBudgets, saveBudget } from '../api/budgets.js'
import { createTransaction } from '../api/transactions.js'
import BudgetCard from '../components/budgets/BudgetCard.jsx'
import BudgetForm from '../components/budgets/BudgetForm.jsx'
import SpendForm from '../components/budgets/SpendForm.jsx'
import SaveStatus from '../components/SaveStatus.jsx'
import { useLoad } from '../hooks/useLoad.js'
import { formatMonth } from '../lib/format.js'
import { categoryLabel } from '../lib/labels.js'
import { todayISO } from '../lib/transactions.js'

// Budgets screen (#27, FR-15, FR-16). The server keeps the budgets and calculates usage,
// status and warnings from the Ledger's expenses; this page shows them and reloads after
// every change. Warnings come from the API in two ways:
//   - the list response says which budgets are at or over a threshold right now;
//   - adding an expense returns the warnings that this expense caused (the BudgetMonitor,
//     an Observer of the Ledger, sends each threshold once).
export default function Budgets() {
  const [month, setMonth] = useState(() => todayISO().slice(0, 7))
  const budgets = useLoad(() => listBudgets(month), month)
  const accounts = useLoad(listAccounts, 'accounts')
  const [save, setSave] = useState({ state: 'idle' })
  const [busy, setBusy] = useState(false)
  // Warnings returned by the last expense added here: [{ category, month, level, message }]
  const [fresh, setFresh] = useState([])

  async function mutate(action) {
    setSave({ state: 'saving' })
    try {
      const result = await action()
      setSave({ state: 'saved' })
      budgets.reload()
      return result
    } catch (error) {
      setSave({ state: 'failed', message: error.message })
      throw error
    }
  }

  async function handleSave(values) {
    setFresh([])
    await mutate(() => saveBudget(values))
    if (values.month !== month) setMonth(values.month) // show the month that was just saved
  }

  async function handleSpend(body) {
    setFresh([])
    const created = await mutate(() => createTransaction(body))
    setFresh(created.warnings ?? [])
  }

  async function handleDelete(budget) {
    setBusy(true)
    setFresh([])
    try {
      await mutate(() => deleteBudget(budget.month, budget.category))
    } catch {
      // SaveStatus already shows the message.
    } finally {
      setBusy(false)
    }
  }

  const data = budgets.data
  let list
  if (budgets.status === 'error' && !data) {
    list = (
      <div className="card state-message state-error" role="alert">
        <h3>Something went wrong</h3>
        <p>{budgets.error?.message}</p>
        <button type="button" className="button" onClick={budgets.reload}>
          Try again
        </button>
      </div>
    )
  } else if (!data) {
    list = (
      <div role="status">
        <span className="sr-only">Loading budgets…</span>
        <div className="card skeleton skeleton-block short" aria-hidden="true" />
      </div>
    )
  } else if (data.budgets.length === 0) {
    list = (
      <div className="card state-message" role="status">
        <h3>No budgets for {formatMonth(month)}</h3>
        <p>Choose a category and a monthly limit above to start tracking your spending.</p>
      </div>
    )
  } else {
    list = (
      <ul className="budget-list" aria-busy={budgets.status === 'loading'}>
        {data.budgets.map((budget) => (
          <BudgetCard
            key={budget.category}
            budget={budget}
            thresholds={data.thresholds}
            onDelete={handleDelete}
            busy={busy}
          />
        ))}
      </ul>
    )
  }

  return (
    <section className="budgets">
      <div className="page-header">
        <h2>Budgets</h2>
        <div className="month-picker">
          <label htmlFor="budget-month">Month</label>
          <input
            id="budget-month"
            type="month"
            value={month}
            onChange={(event) => {
              if (event.target.value) {
                setFresh([])
                setMonth(event.target.value)
              }
            }}
          />
        </div>
      </div>

      <SaveStatus save={save} />

      {data && (
        <p className="field-hint">
          You get a warning when a budget reaches {data.thresholds.warning}% of its limit and another at{' '}
          {data.thresholds.exceeded}%. Only expenses count; income and transfers never use up a budget.
        </p>
      )}

      {fresh.length > 0 && (
        <div className="budget-alert" role="alert">
          <h3>New budget warning</h3>
          <ul>
            {fresh.map((warning) => (
              <li key={`${warning.category}-${warning.month}-${warning.level}`}>
                {warning.message} ({formatMonth(warning.month)}): the {warning.level}% threshold was just passed.
              </li>
            ))}
          </ul>
          <button type="button" className="link-button" onClick={() => setFresh([])}>
            Dismiss
          </button>
        </div>
      )}

      {data && data.warnings.length > 0 && (
        <div className="budget-alert budget-alert-current" role="status">
          <h3>Budgets over a threshold in {formatMonth(month)}</h3>
          <ul>
            {data.warnings.map((warning) => (
              <li key={warning.category}>
                {categoryLabel(warning.category)}: {warning.message} ({warning.level}% threshold passed)
              </li>
            ))}
          </ul>
        </div>
      )}

      <BudgetForm key={month} month={month} onSubmit={handleSave} />

      {list}

      {accounts.data && accounts.data.length > 0 && <SpendForm accounts={accounts.data} onSubmit={handleSpend} />}
      {accounts.data && accounts.data.length === 0 && (
        <p className="field-hint">Add an account on the Accounts page to record spending.</p>
      )}
    </section>
  )
}
