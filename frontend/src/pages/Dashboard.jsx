import { useState } from 'react'
import { DEFAULT_MONTH } from '../api/dashboard.js'
import { getNetWorth } from '../api/accounts.js'
import { reportExport } from '../api/exports.js'
import CsvDownload from '../components/CsvDownload.jsx'
import { useDashboard } from '../hooks/useDashboard.js'
import { useLoad } from '../hooks/useLoad.js'
import NetWorthCard from '../components/NetWorthCard.jsx'
import MonthPicker from '../components/dashboard/MonthPicker.jsx'
import SummaryCards from '../components/dashboard/SummaryCards.jsx'
import IncomeExpenseChart from '../components/dashboard/IncomeExpenseChart.jsx'
import CategoryBreakdown from '../components/dashboard/CategoryBreakdown.jsx'
import RecentTransactions from '../components/dashboard/RecentTransactions.jsx'
import {
  DashboardEmpty,
  DashboardError,
  DashboardLoading,
} from '../components/dashboard/DashboardStates.jsx'

export default function Dashboard() {
  const [month, setMonth] = useState(DEFAULT_MONTH)
  const { status, data, error, retry } = useDashboard(month)
  const months = data?.availableMonths ?? [month]
  // Re-read on every visit, so it reflects mutations made on the Accounts page.
  const netWorth = useLoad(getNetWorth, 'net-worth')

  return (
    <section className="dashboard" aria-labelledby="dashboard-title">
      <header className="page-header">
        <h2 id="dashboard-title">Dashboard</h2>
        <MonthPicker months={months} value={month} onChange={setMonth} disabled={!data} />
      </header>

      <NetWorthCard net={netWorth} />

      <div className="card">
        <CsvDownload
          key={month}
          defaultFilename={`monthly-report-${month}.csv`}
          label="Download report CSV"
          disabled={!data || data.month !== month || !['success', 'empty'].includes(status)}
          buildExport={() => reportExport(data)}
        />
      </div>

      {status === 'loading' && <DashboardLoading />}
      {status === 'error' && <DashboardError message={error.message} onRetry={retry} />}
      {status === 'empty' && <DashboardEmpty month={month} />}
      {status === 'success' && (
        <>
          <SummaryCards summary={data.summary} />
          <div className="dashboard-grid">
            <IncomeExpenseChart trend={data.trend} />
            <CategoryBreakdown categories={data.categories} />
          </div>
          <RecentTransactions transactions={data.recentTransactions} />
        </>
      )}
    </section>
  )
}
