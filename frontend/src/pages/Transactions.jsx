import { useState } from 'react'
import { transactionExport } from '../api/exports.js'
import CsvDownload from '../components/CsvDownload.jsx'
import { FILTER_ACCOUNTS, FILTER_CATEGORIES, FILTER_KINDS, FILTER_TRANSACTIONS } from '../fixtures/transactions.js'
import { formatDate } from '../lib/format.js'
import { formatEUR } from '../lib/money.js'
import { emptyFilters, selectTransactions, validateFilters } from '../lib/transactionFilters.js'
import './Transactions.css'

const titleCase = (text) => text[0].toUpperCase() + text.slice(1)
const accountName = (id) => FILTER_ACCOUNTS.find((account) => account.id === id)?.name ?? String(id)

export default function Transactions() {
  const [filters, setFilters] = useState(emptyFilters)
  const { errors } = validateFilters(filters)
  const invalid = Object.keys(errors).length > 0
  const results = selectTransactions(FILTER_TRANSACTIONS, filters)
  const update = (key, value) => setFilters((previous) => ({ ...previous, [key]: value }))
  const active = [
    ...filters.categories.map((category) => `Category: ${category}`),
    filters.kind && `Type: ${titleCase(filters.kind)}`,
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

  return (
    <section className="transaction-filters-page" aria-labelledby="transactions-title">
      <div className="page-header">
        <h2 id="transactions-title">Transactions</h2>
        <span>Synthetic preview</span>
      </div>
      <p>Combine filters to explore sample transactions. Changes here do not affect saved accounts.</p>
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
            {FILTER_CATEGORIES.map((category) => (
              <label key={category}>
                <input type="checkbox" checked={filters.categories.includes(category)} onChange={() => toggleCategory(category)} />
                {category}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="filter-grid">
          <div className="field">
            <label htmlFor="filter-kind">Type</label>
            <select id="filter-kind" value={filters.kind} onChange={(event) => update('kind', event.target.value)}>
              <option value="">All types</option>
              {FILTER_KINDS.map((kind) => <option key={kind} value={kind}>{titleCase(kind)}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="filter-account">Account</label>
            <select id="filter-account" value={filters.account} onChange={(event) => update('account', event.target.value)}>
              <option value="">All accounts</option>
              {FILTER_ACCOUNTS.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
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
        {active.length ? <ul className="active-filters">{active.map((label) => <li key={label}>{label}</li>)}</ul> : <p>No filters — showing all sample transactions.</p>}
      </div>
      <div className="card">
        <CsvDownload
          defaultFilename="transactions.csv"
          label="Download transactions CSV"
          disabled={invalid}
          buildExport={() => transactionExport(results, filters)}
        />
        <p role="status">{invalid ? 'Correct the filter values to see results.' : `${results.length} of ${FILTER_TRANSACTIONS.length} transactions · Sorted by ${filters.sortKey}, ${filters.sortDirection === 'desc' ? 'descending' : 'ascending'}`}</p>
        {invalid ? <p role="alert">The filter range is invalid. Check the highlighted fields.</p> : results.length === 0 ? (
          <div className="state-message">
            <h3>No matching transactions</h3>
            <p>Broaden your filters or reset filters and sorting to show all sample transactions.</p>
          </div>
        ) : (
          <div className="table-scroll" role="region" aria-label="Filtered transactions" tabIndex={0}>
            <table className="data-table">
              <caption className="sr-only">Sample transactions matching every active filter</caption>
              <thead><tr><th scope="col">Date</th><th scope="col">Account</th><th scope="col">Category</th><th scope="col">Type</th><th scope="col">Note</th><th scope="col" className="num">Amount</th></tr></thead>
              <tbody>{results.map((transaction) => {
                const negative = transaction.kind === 'expense' || transaction.direction === 'out'
                return (
                  <tr key={transaction.id}>
                    <td>{formatDate(transaction.date)}</td>
                    <td>{accountName(transaction.account_id)}</td>
                    <td>{transaction.category}</td>
                    <td>{titleCase(transaction.kind)}{transaction.kind === 'transfer' && ` (${transaction.direction})`}</td>
                    <th scope="row">{transaction.note}</th>
                    <td className="num">{formatEUR(`${negative ? '-' : ''}${transaction.amount}`, { signed: true })}</td>
                  </tr>
                )
              })}</tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}
