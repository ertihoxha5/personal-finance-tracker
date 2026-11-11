import { formatMonth } from '../../lib/format.js'

export default function MonthPicker({ months, value, onChange, disabled }) {
  return (
    <div className="month-picker">
      <label htmlFor="dashboard-month">Month</label>
      <select
        id="dashboard-month"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
      >
        {months.map((month) => (
          <option key={month} value={month}>
            {formatMonth(month)}
          </option>
        ))}
      </select>
    </div>
  )
}
