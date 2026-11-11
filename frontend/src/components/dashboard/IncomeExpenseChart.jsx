import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { EXPENSE_COLOR, INCOME_COLOR } from '../../lib/chartColors.js'
import { formatEUR, formatMonth, formatShortMonth } from '../../lib/format.js'

export default function IncomeExpenseChart({ trend }) {
  // Recharts needs numbers; convert the decimal strings only for rendering.
  const chartData = trend.map((point) => ({
    label: formatShortMonth(point.month),
    income: Number(point.income),
    expenses: Number(point.expenses),
  }))

  return (
    <section className="card chart-card" aria-labelledby="trend-title">
      <h3 id="trend-title">Income vs expenses</h3>
      <div className="chart" aria-hidden="true">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" />
            <YAxis tickFormatter={(value) => `€${value}`} width={64} />
            <Tooltip formatter={(value) => formatEUR(value)} />
            <Legend itemSorter={null} />
            <Bar dataKey="income" name="Income" fill={INCOME_COLOR} />
            <Bar dataKey="expenses" name="Expenses" fill={EXPENSE_COLOR} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only">
        <caption>Income and expenses by month</caption>
        <thead>
          <tr>
            <th scope="col">Month</th>
            <th scope="col">Income</th>
            <th scope="col">Expenses</th>
          </tr>
        </thead>
        <tbody>
          {trend.map((point) => (
            <tr key={point.month}>
              <th scope="row">{formatMonth(point.month)}</th>
              <td>{formatEUR(point.income)}</td>
              <td>{formatEUR(point.expenses)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
