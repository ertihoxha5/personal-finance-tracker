import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { fetchOptionalFeatures, optionalEnabled } from '../api/optional.js'

const LINKS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/transactions', label: 'Transactions' },
  { to: '/budgets', label: 'Budgets' },
  { to: '/accounts', label: 'Accounts' },
]

export default function Layout() {
  const [apiStatus, setApiStatus] = useState('checking')
  const [showTools, setShowTools] = useState(false)

  useEffect(() => {
    let active = true
    fetchOptionalFeatures().then((features) => { if (active) setShowTools(optionalEnabled(features)) }).catch(() => {})
    return () => { active = false }
  }, [])

  useEffect(() => {
    fetch('/api/health')
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((body) => setApiStatus(body.status))
      .catch(() => setApiStatus('offline'))
  }, [])

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1 className="brand">Finance Tracker</h1>
        <nav>
          {LINKS.map(({ to, label, end }) => (
            <NavLink key={to} to={to} end={end} className="nav-link">
              {label}
            </NavLink>
          ))}
          {showTools && <NavLink to="/tools" className="nav-link">Optional tools</NavLink>}
        </nav>
        <p className={`api-status api-${apiStatus}`}>API: {apiStatus}</p>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
