import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Transactions from './pages/Transactions.jsx'
import Budgets from './pages/Budgets.jsx'
import Accounts from './pages/Accounts.jsx'
import DevMoney from './pages/DevMoney.jsx'
import DevErrors from './pages/DevErrors.jsx'
import DevValidation from './pages/DevValidation.jsx'
import DevTransactions from './pages/DevTransactions.jsx'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="transactions" element={<Transactions />} />
        <Route path="budgets" element={<Budgets />} />
        <Route path="accounts" element={<Accounts />} />
        {import.meta.env.DEV && <Route path="dev/money" element={<DevMoney />} />}
        {import.meta.env.DEV && <Route path="dev/errors" element={<DevErrors />} />}
        {import.meta.env.DEV && <Route path="dev/validation" element={<DevValidation />} />}
        {import.meta.env.DEV && <Route path="dev/transactions" element={<DevTransactions />} />}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
