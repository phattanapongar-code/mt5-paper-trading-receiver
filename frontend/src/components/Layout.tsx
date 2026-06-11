import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const navItems = [
  { to: '/', label: 'Overview', icon: '◉' },
  { to: '/charts', label: 'Charts', icon: '▤' },
  { to: '/bots', label: 'Bots', icon: '◈' },
  { to: '/compare', label: 'Compare', icon: '⇄' },
  { to: '/trades', label: 'Trades', icon: '≡' },
  { to: '/signals', label: 'Signals', icon: '⚡' },
  { to: '/performance', label: 'Performance', icon: '◐' },
  { to: '/wallets', label: 'Wallets', icon: '◐' },
  { to: '/market-structure', label: 'Structure', icon: '◈' },
  { to: '/pending-orders', label: 'Pending', icon: '◷' },
  { to: '/settings', label: 'Settings', icon: '⚙' },
]

export default function Layout() {
  const { logout } = useAuth()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden">
      <aside
        className={`flex flex-col bg-surface-800 border-r border-surface-500 transition-all duration-200 ${
          collapsed ? 'w-16' : 'w-56'
        }`}
      >
        <div className="flex items-center gap-2 h-13 px-4 border-b border-surface-500 shrink-0">
          {!collapsed && (
            <span className="font-mono text-xs tracking-widest text-cyber-cyan font-semibold uppercase">
              MT5 Dashboard
            </span>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="ml-auto text-text-muted hover:text-text-primary cursor-pointer text-lg leading-none"
          >
            {collapsed ? '▸' : '◂'}
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto py-2 px-1 space-y-0.5">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-cyber-cyan/10 text-cyber-cyan border-l-2 border-cyber-cyan'
                    : 'text-text-secondary hover:bg-surface-600 hover:text-text-primary border-l-2 border-transparent'
                }`
              }
            >
              <span className="w-5 text-center text-base shrink-0">{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="p-3 border-t border-surface-500 shrink-0">
          <button
            onClick={logout}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-md text-sm text-text-muted hover:bg-surface-600 hover:text-cyber-red transition-colors cursor-pointer"
          >
            <span className="w-5 text-center shrink-0">↩</span>
            {!collapsed && <span>Logout</span>}
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto bg-surface-900">
        <Outlet />
      </main>
    </div>
  )
}
