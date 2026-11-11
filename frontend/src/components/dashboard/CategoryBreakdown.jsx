import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { EXPENSE_COLOR } from '../../lib/chartColors.js'
import { formatEUR } from '../../lib/money.js'

const ROW_HEIGHT = 34

export default function CategoryBreakdown({ categories }) {
  const chartData = categories.map((category) => ({
    name: category.name,
    total: Number(category.total),
  }))

  return (
    <section className="card chart-card" aria-labelledby="categories-title">
      <h3 id="categories-title">Spending by category</h3>
      <div className="chart" aria-hidden="true">
        <ResponsiveContainer width="100%" height={chartData.length * ROW_HEIGHT + 32}>
          <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
            <XAxis type="number" tickFormatter={(value) => `€${value}`} />
            <YAxis type="category" dataKey="name" width={112} tick={{ fontSize: 13 }} />
            <Tooltip formatter={(value) => formatEUR(value)} />
            <Bar dataKey="total" name="Spent" fill={EXPENSE_COLOR} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="data-table compact">
        <caption className="sr-only">Spending by category this month</caption>
        <thead>
          <tr>
            <th scope="col">Category</th>
            <th scope="col" className="num">
              Spent
            </th>
          </tr>
        </thead>
        <tbody>
          {categories.map((category) => (
            <tr key={category.id}>
              <th scope="row">{category.name}</th>
              <td className="num">{formatEUR(category.total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
