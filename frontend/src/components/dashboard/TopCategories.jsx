import { formatEUR } from '../../lib/money.js'

// The three biggest spending categories of the month, as the server ranked them.
export default function TopCategories({ categories }) {
  return (
    <section className="card" aria-labelledby="top-categories-title">
      <h3 id="top-categories-title">Top spending categories</h3>
      {categories.length === 0 ? (
        <p className="summary-meta">No spending this month.</p>
      ) : (
        <ol className="top-categories">
          {categories.map((category) => (
            <li key={category.id}>
              <span>{category.name}</span>
              <span className="amount">{formatEUR(category.total)}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
