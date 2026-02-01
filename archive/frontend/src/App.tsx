import { useState } from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Explorer from './pages/Explorer'
import Simulator from './pages/Simulator'
import RGPD from './pages/RGPD'
import Cost from './pages/Cost'
import './App.css'

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
        <div className="sidebar-header">
          <h1>👜 LVMH</h1>
          <span className="subtitle">Voice to Tag</span>
        </div>

        <nav className="sidebar-nav">
          <NavLink to="/" className={({ isActive }) => isActive ? 'active' : ''}>
            📊 Dashboard
          </NavLink>
          <NavLink to="/explorer" className={({ isActive }) => isActive ? 'active' : ''}>
            🔍 Explorer
          </NavLink>
          <NavLink to="/simulator" className={({ isActive }) => isActive ? 'active' : ''}>
            🧪 Simulator
          </NavLink>
          <NavLink to="/rgpd" className={({ isActive }) => isActive ? 'active' : ''}>
            🛡️ RGPD
          </NavLink>
          <NavLink to="/cost" className={({ isActive }) => isActive ? 'active' : ''}>
            💰 Cost & ROI
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          <span>v2.0 • Janvier 2026</span>
        </div>
      </aside>

      {/* Main content */}
      <main className="main-content">
        <button
          className="sidebar-toggle"
          onClick={() => setSidebarOpen(!sidebarOpen)}
        >
          {sidebarOpen ? '◀' : '▶'}
        </button>

        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/explorer" element={<Explorer />} />
          <Route path="/simulator" element={<Simulator />} />
          <Route path="/rgpd" element={<RGPD />} />
          <Route path="/cost" element={<Cost />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
