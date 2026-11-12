import { useState } from 'react'
import { listAccounts } from '../api/accounts.js'
import { transactionExport } from '../api/exports.js'
import { createTransaction, fromApi, searchTransactions, transactionQuery } from '../api/transactions.js'
import CsvDownload from '../components/CsvDownload.jsx'
import SaveStatus from '../components/SaveStatus.jsx'
import TransactionForm from '../components/transactions/TransactionForm.jsx'
import TransactionRows from '../components/transactions/TransactionRows.jsx'
import { useDebounced } from '../hooks/useDebounced.js'
import { useLoad } from '../hooks/useLoad.js'
import { CATEGORY_LABELS, KIND_LABELS, categoryLabel, kindLabel } from '../lib/labels.js'
import { emptyFilters, validateFilters } from '../lib/transactionFilters.js'
import './Transactions.css'

// Transactions screen (#21). Filtering and sorting run on the server with the Python
// predicates (#8, #15); this page sends the filters as a query and shows what comes back.
// The add form posts to the API, which saves to SQLite before it answers.
export default function Transactions() {
  const [filters, setFilters] = useState(emptyFilters)
  const [save, setSave] = useState({ state: 'idle' })
  const { errors } = validateFilters(filters)
  const invalid = Object.keys(errors).length > 0

  const accounts = useLoad(listAccounts, 'accounts')
  // Wait for typing to pause, so the note search sends one request, not one per key.
  const query = useDebounced(transactionQuery(filters))
  const results = useLoad(
    () => (invalid ? Promise.resolve(null) : searchTransactions(filters)),
    `${invalid}|${query}`,
  )

  const update = (key, value) => setFilters((previous) => ({ ...previous, [key]: value }))
  const accountName = (id) => accounts.data?.find((account) => account.id === id)?.name ?? `Account ${id}`
  const rows = results.data ? results.data.map(fromApi) : null
  const sortDescription = `Sorted by ${filters.sortKey}, ${filters.sortDirection === 'desc' ? 'descending' : 'ascending'}`

  const active = [
    ...filters.categories.map((category) => `Category: ${categoryLabel(category)}`),
    filters.kind && `Type: ${kindLabel(filters.kind)}`,
    filters.account && `Account: ${accountName(Number(filters.account))}`,
    filters.start && `From: ${filters.start}`,
    filters.end && `To: ${filters.end}`,
    filters.minimum && `Minimum: ${filters.minimum} EUR`,
    filters.maximum && `Maximum: ${filters.maximum} EUR`,
    filters.note.trim() && `Note: ${filters.note.trim()}`,
  ].filter(Boolean)

  function toggleCategory(category) {
    setFilters((previous) => ({
      ...previous,
      categories: previous.categories.includes(category)
        ? previous.categories.filter((value) => value !== category)
        : [...previous.categories, category],
    }))
  }

  // The form shows server errors under the field they belong to; this adds the save status
  // and refreshes the list (and the account balances) once the change is stored.
  async function handleCreate(body) {
    setSave({ state: 'saving' })
    try {
      await createTransaction(body)
    } catch (error) {
      setSave({ state: 'failed', message: error.message })
      throw error
    }
    setSave({ state: 'saved' })
    results.reload()
  }

  function field(key, label, type = 'text', placeholder) {
    return (
      <div className="field">
        <label htmlFor={`filter-${key}`}>{label}</label>
        <input
          id={`filter-${key}`} type={type} value={filters[key]}
          placeholder={placeholder}
          inputMode={key === 'minimum' || key === 'maximum' ? 'decimal' : undefined}
          onChange={(event) => update(key, event.target.value)}
          aria-invalid={Boolean(errors[key])}
          aria-describedby={errors[key] ? `filter-${key}-error` : undefined}
        />
        {errors[key] && <p className="field-error" id={`filter-${key}-error`}>{errors[key]}</p>}
      </div>
    )
  }

  let listing
  if (invalid) {
    listing = <p role="alert">The filter range is invalid. Check the highlighted fields.</p>
  } else if (results.status === 'error' && !rows) {
    listing = (
      <div className="state-message state-error" role="alert">
        <h3>Something went wrong</h3>
        <p>{results.error?.message}</p>
        <button type="button" className="button" onClick={results.reload}>Try again</button>
      </div>
    )
  } else if (!rows) {
    listing = (
      <div role="status">
        <span className="sr-only">Loading transactions…</span>
        <div className="skeleton skeleton-block short" aria-hidden="true" />
      </div>
    )
  } else if (rows.length === 0) {
    listing = (
      <div className="state-message" role="status">
        <h3>{active.length ? 'No matching transactions' : 'No transactions yet'}</h3>
        <p>
          {active.length
            ? 'Broaden your filters or reset filters and sorting to show everything.'
            : 'Add your first income or expense with the form above.'}
        </p>
      </div>
    )
  } else {
    listing = (
      <TransactionRows transactions={rows} accountName={accountName} caption="Transactions matching every active filter" />
    )
  }

  return (
    <section className="transaction-filters-page" aria-labelledby="transactions-title">
      <div className="page-header">
        <h2 id="transactions-title">Transactions</h2>
      </div>

      <SaveStatus save={save} />
      {accounts.status === 'error' && !accounts.data ? (
        <div className="card state-message state-error" role="alert">
          <p>{accounts.error?.message}</p>
          <button type="button" className="button" onClick={accounts.reload}>Try again</button>
        </div>
      ) : accounts.data && accounts.data.length === 0 ? (
        <div className="card state-message" role="status">
          <h3>No accounts yet</h3>
          <p>Add an account on the Accounts page before adding transactions.</p>
        </div>
      ) : accounts.data ? (
        <TransactionForm accounts={accounts.data} onSubmit={handleCreate} />
      ) : null}

      <form className="card" aria-labelledby="filters-title" onSubmit={(event) => event.preventDefault()}>
        <div className="page-header">
          <h3 id="filters-title">Filter transactions</h3>
          <button type="button" className="button button-secondary" onClick={() => setFilters(emptyFilters())}>
            Reset filters and sorting
          </button>
        </div>
        <fieldset>
          <legend>Categories (choose any)</legend>
          <div className="category-options">
            {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
              <label key={value}>
                <input type="checkbox" checked={filters.categories.includes(value)} onChange={() => toggleCategory(value)} />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="filter-grid">
          <div className="field">
            <label htmlFor="filter-kind">Type</label>
            <select id="filter-kind" value={filters.kind} onChange={(event) => update('kind', event.target.value)}>
              <option value="">All types</option>
              {Object.entries(KIND_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="filter-account">Account</label>
            <select id="filter-account" value={filters.account} onChange={(event) => update('account', event.target.value)}>
              <option value="">All accounts</option>
              {(accounts.data ?? []).map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
            </select>
          </div>
          {field('start', 'Start date', 'date')}
          {field('end', 'End date', 'date')}
          {field('minimum', 'Minimum amount (EUR)')}
          {field('maximum', 'Maximum amount (EUR)')}
          {field('note', 'Search notes', 'search', 'Search notes, e.g. lunch')}
          <div className="field">
            <label htmlFor="transaction-sort-key">Sort by</label>
            <select
              id="transaction-sort-key"
              value={filters.sortKey}
              onChange={(event) => update('sortKey', event.target.value)}
            >
              <option value="date">Date</option>
              <option value="amount">Amount</option>
              <option value="category">Category</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="transaction-sort-direction">Sort direction</label>
            <select
              id="transaction-sort-direction"
              value={filters.sortDirection}
              onChange={(event) => update('sortDirection', event.target.value)}
            >
              <option value="asc">Ascending</option>
              <option value="desc">Descending</option>
            </select>
          </div>
        </div>
        <p className="field-hint">Filters apply together. Dates and amount bounds are inclusive. Amounts use magnitudes, including expenses and transfers.</p>
      </form>
      <div className="card">
        <h3>Active filters</h3>
        {active.length ? <ul className="active-filters">{active.map((label) => <li key={label}>{label}</li>)}</ul> : <p>No filters — showing all transactions.</p>}
      </div>
      <div className="card" aria-busy={results.status === 'loading'}>
        <CsvDownload
          defaultFilename="transactions.csv"
          label="Download transactions CSV"
          disabled={invalid || !rows}
          buildExport={() => transactionExport(results.data, filters)}
        />
        <p role="status">
          {invalid
            ? 'Correct the filter values to see results.'
            : rows
              ? `${rows.length} transaction${rows.length === 1 ? '' : 's'} · ${sortDescription}`
              : ''}
        </p>
        {listing}
      </div>
    </section>
  )
}
