import { useEffect, useState } from 'react'
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fetchCategoryReport } from '../../api/categoryReport.js'
import { useLoad } from '../../hooks/useLoad.js'
import { EXPENSE_COLOR } from '../../lib/chartColors.js'
import { formatDate } from '../../lib/format.js'
import { formatEUR } from '../../lib/money.js'

const ROW_HEIGHT = 34
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

// "2026-11" -> { start: "2026-11-01", end: "2026-11-30" }. String and UTC date work only.
function monthRange(month) {
  const [year, number] = month.split('-').map(Number)
  const lastDay = new Date(Date.UTC(year, number, 0)).getUTCDate()
  return { start: `${month}-01`, end: `${month}-${String(lastDay).padStart(2, '0')}` }
}

// Returns a message for a range that cannot be sent, or null when it is fine.
function rangeProblem(start, end) {
  if (!ISO_DATE.test(start) || !ISO_DATE.test(end)) return 'Enter both a start and an end date.'
  if (start > end) return 'The start date must be on or before the end date.'
  return null
}

export default function CategoryBreakdown({ month }) {
  const [range, setRange] = useState(() => monthRange(month))
  // Follow the Dashboard month picker; the user can then still adjust the dates freely.
  useEffect(() => {
    if (month) setRange(monthRange(month))
  }, [month])

  const problem = rangeProblem(range.start, range.end)
  const report = useLoad(
    () => (problem ? Promise.resolve(null) : fetchCategoryReport(range.start, range.end)),
    `${range.start}|${range.end}`,
  )
  const update = (field) => (event) => setRange((prev) => ({ ...prev, [field]: event.target.value }))

  const data = problem ? null : report.data
  const categories = data?.categories ?? []
  const chartData = categories.map((c) => ({ name: c.name, total: Number(c.total) }))

  return (
    <section className="card chart-card" aria-labelledby="categories-title">
      <h3 id="categories-title">Spending by category</h3>

      <div className="range-picker">
        <div className="range-field">
          <label htmlFor="category-start">From</label>
          <input
            id="category-start"
            type="date"
            value={range.start}
            onChange={update('start')}
            aria-invalid={problem ? 'true' : undefined}
            aria-describedby={problem ? 'category-range-error' : undefined}
          />
        </div>
        <div className="range-field">
          <label htmlFor="category-end">To</label>
          <input
            id="category-end"
            type="date"
            value={range.end}
            onChange={update('end')}
            aria-invalid={problem ? 'true' : undefined}
            aria-describedby={problem ? 'category-range-error' : undefined}
          />
        </div>
      </div>

      {problem && (
        <p id="category-range-error" className="field-error" role="alert">
          {problem}
        </p>
      )}
      {!problem && report.status === 'loading' && !data && <p role="status">Loading categories…</p>}
      {!problem && report.status === 'error' && (
        <div role="alert">
          <p>{report.error.message}</p>
          <button type="button" className="button" onClick={report.reload}>
            Try again
          </button>
        </div>
      )}
      {data && categories.length === 0 && (
        <p role="status">
          No spending between {formatDate(data.start)} and {formatDate(data.end)}.
        </p>
      )}

      {data && categories.length > 0 && (
        <>
          <div className="chart" aria-hidden="true">
            <ResponsiveContainer width="100%" height={chartData.length * ROW_HEIGHT + 32}>
              <BarChart
                data={chartData}
                layout="vertical"
                margin={{ top: 0, right: 16, left: 0, bottom: 0 }}
              >
                <XAxis type="number" tickFormatter={(value) => `€${value}`} />
                <YAxis type="category" dataKey="name" width={112} tick={{ fontSize: 13 }} />
                <Tooltip formatter={(value) => formatEUR(value)} />
                <Bar dataKey="total" name="Spent" fill={EXPENSE_COLOR} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <table className="data-table compact">
            <caption className="sr-only">
              Spending by category from {formatDate(data.start)} to {formatDate(data.end)}
            </caption>
            <thead>
              <tr>
                <th scope="col">Category</th>
                <th scope="col" className="num">
                  Spent
                </th>
                <th scope="col" className="num">
                  Share
                </th>
              </tr>
            </thead>
            <tbody>
              {categories.map((c) => (
                <tr key={c.id}>
                  <th scope="row">{c.name}</th>
                  <td className="num">{formatEUR(c.total)}</td>
                  <td className="num">{c.percent}%</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row">Total</th>
                <td className="num">{formatEUR(data.total)}</td>
                <td className="num">100.0%</td>
              </tr>
            </tfoot>
          </table>
        </>
      )}
    </section>
  )
}
