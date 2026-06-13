import { useState, useEffect } from 'react'
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useBotContext } from '../context/BotContext'
import { useTheme } from '../context/ThemeContext'
import { FiCircle, FiBarChart2, FiClipboard, FiDollarSign, FiBell, FiTrendingUp, FiSettings, FiPlay, FiSearch, FiClock, FiLayers, FiMenu, FiChevronRight, FiChevronLeft, FiX, FiSun, FiMoon, FiLogOut, FiActivity } from 'react-icons/fi'
import { FaRobot, FaBalanceScale } from 'react-icons/fa'
import type { IconType } from 'react-icons'
import type { Bot } from '../types/api'

const paperNavItems: { to: string; label: string; icon: IconType }[] = [
  { to: '/', label: 'Overview', icon: FiCircle },
  { to: '/charts', label: 'Charts', icon: FiBarChart2 },
  { to: '/bots', label: 'Bots', icon: FaRobot },
  { to: '/compare', label: 'Compare', icon: FaBalanceScale },
  { to: '/trades', label: 'Trade History', icon: FiClipboard },
  { to: '/trade', label: 'Manual Trade', icon: FiDollarSign },
  { to: '/signals', label: 'Signals', icon: FiBell },
  { to: '/performance', label: 'Performance', icon: FiTrendingUp },
  { to: '/market-structure', label: 'Structure', icon: FiLayers },
  { to: '/pending-orders', label: 'Pending', icon: FiClock },
]

const liveNavItems: { to: string; label: string; icon: IconType }[] = [
  { to: '/live', label: 'Live Trading', icon: FiActivity },
  { to: '/live/history', label: 'Live History', icon: FiClipboard },
]

const bottomNavItems: { to: string; label: string; icon: IconType }[] = [
  { to: '/settings', label: 'Settings', icon: FiSettings },
  { to: '/replay', label: 'Replay', icon: FiPlay },
  { to: '/backtest', label: 'Backtest', icon: FiSearch },
]

const STRATEGY_COLORS: Record<string, string> = {
  trend_ob: '#FCD535',
  rsi_meanrev: '#0ecb81',
  macd_cross: '#5e7cc4',
}

function isBotLive(bot: Bot): boolean {
  return !!bot.runtime_updated_at && (Date.now() / 1000 - bot.runtime_updated_at) < 12
}

export default function Layout() {
  const { logout } = useAuth()
  const { allBots, selectedBot, setSelectedBot, symbol, setSymbol, symbols } = useBotContext()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const location = useLocation()

  // Close mobile sidebar on navigation
  useEffect(() => { setMobileOpen(false) }, [location.pathname])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return
      switch (e.key) {
        case '1': navigate('/'); break
        case '2': navigate('/charts'); break
        case '3': navigate('/bots'); break
        case '4': navigate('/compare'); break
        case '5': navigate('/trades'); break
        case '6': navigate('/trade'); break
        case '7': navigate('/signals'); break
        case '8': navigate('/performance'); break
        case '9': navigate('/market-structure'); break
        case '0': navigate('/live'); break
        case 'b': setCollapsed(c => !c); break
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [navigate])

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile hamburger + header bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 flex items-center gap-2 h-[52px] px-3 bg-surface-card-dark border-b border-hairline-on-dark">
          <button
            onClick={() => setMobileOpen(true)}
            className="text-body hover:text-primary cursor-pointer text-xl leading-none p-1"
          >
            <FiMenu size={18} />
          </button>
        <span className="font-sans text-xs tracking-widest text-primary font-bold uppercase">
          PAPER TRADING
        </span>
          <button
            onClick={() => setMobileOpen(true)}
            className="ml-auto text-muted hover:text-body cursor-pointer text-lg leading-none"
          >
            <FiMenu size={18} />
          </button>
      </div>

      {/* Mobile overlay backdrop */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 z-30 bg-black/50"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          flex flex-col bg-surface-card-dark border-r border-hairline-on-dark transition-all duration-200
          ${collapsed ? 'w-16' : 'w-56'}
          fixed md:relative z-40 h-full
          ${mobileOpen ? 'left-0' : '-left-64 md:left-0'}
        `}
      >
        <div className="flex items-center gap-2 h-[52px] px-4 border-b border-hairline-on-dark shrink-0">
          {!collapsed && (
            <span className="font-sans text-xs tracking-widest text-primary font-bold uppercase">
              PAPER TRADING
            </span>
          )}
          {collapsed && selectedBot && (
            <span className={`text-primary font-mono text-sm font-semibold truncate relative ${isBotLive(selectedBot) ? 'after:absolute after:-top-0.5 after:-right-0.5 after:w-2 after:h-2 after:bg-trading-up after:rounded-full after:shadow-[0_0_4px_#0ecb81]' : ''}`} title={selectedBot.name}>
              {selectedBot.name.slice(0, 2).toUpperCase()}
            </span>
          )}
          {collapsed && !selectedBot && (
            <span className="text-xs text-muted font-mono ml-0.5" title="All Bots">A</span>
          )}
          {!collapsed && !selectedBot && (
            <span className="text-xs text-muted font-mono ml-0.5">All</span>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="ml-auto text-muted hover:text-body cursor-pointer text-lg leading-none"
          >
            {collapsed ? <FiChevronRight size={16} /> : <FiChevronLeft size={16} />}
          </button>
          {/* Mobile close button */}
          <button
            onClick={() => setMobileOpen(false)}
            className="md:hidden text-muted hover:text-body cursor-pointer text-lg leading-none"
          >
            <FiX size={16} />
          </button>
        </div>

        {!collapsed && allBots.length > 0 && (
          <div className="px-3 py-1.5 border-b border-hairline-on-dark">
            <select
              value={selectedBot?.id ?? ''}
              onChange={(e) => setSelectedBot(e.target.value ? Number(e.target.value) : null)}
              className="w-full bg-surface-elevated-dark border border-hairline-on-dark text-body text-xs rounded py-1 px-2 cursor-pointer outline-none"
            >
              <option value="">All Bots</option>
              {allBots.map((bot) => (
                <option key={bot.id} value={bot.id}>
                  {bot.name}
                </option>
              ))}
            </select>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {allBots.map((bot) => (
                <BotChip
                  key={bot.id}
                  bot={bot}
                  isActive={selectedBot?.id === bot.id}
                  onClick={() => setSelectedBot(bot.id)}
                  size="sm"
                />
              ))}
            </div>
          </div>
        )}

        {/* Symbol selector */}
        {!collapsed && (
          <div className="px-3 py-2 border-b border-hairline-on-dark">
            <label className="text-[10px] text-muted tracking-wider uppercase font-semibold block mb-1">Symbol</label>
            <select
              value={symbol}
              onChange={e => setSymbol(e.target.value)}
              className="w-full bg-surface-elevated-dark border border-hairline-on-dark text-body text-xs rounded py-1 px-2 cursor-pointer outline-none"
            >
              {symbols.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        )}
        {collapsed && (
          <div className="px-3 py-2 border-b border-hairline-on-dark text-center">
            <span className="text-[10px] text-muted font-mono" title={symbol}>{symbol.slice(0, 3).toUpperCase()}</span>
          </div>
        )}

        <nav className="flex-1 overflow-y-auto py-2 px-1 space-y-0.5">
          {/* Paper Trading */}
          {!collapsed && (
            <div className="px-3 py-1.5 text-[10px] text-muted uppercase tracking-widest font-semibold">Paper Trading</div>
          )}
          {paperNavItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-primary/10 text-primary border-l-2 border-primary'
                    : 'text-muted hover:bg-surface-card-dark hover:text-body border-l-2 border-transparent'
                }`
              }
            >
              <span className="w-5 text-center shrink-0"><item.icon size={16} /></span>
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          ))}

          {/* Separator */}
          {!collapsed && (
            <div className="my-2 mx-3 border-t border-hairline-on-dark/50" />
          )}

          {/* Live Trading */}
          {!collapsed && (
            <div className="px-3 py-1.5 text-[10px] text-trading-up uppercase tracking-widest font-semibold">Live Trading</div>
          )}
          {liveNavItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-trading-up/10 text-trading-up border-l-2 border-trading-up'
                    : 'text-muted hover:bg-surface-card-dark hover:text-body border-l-2 border-transparent'
                }`
              }
            >
              <span className="w-5 text-center shrink-0"><item.icon size={16} /></span>
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          ))}

          {/* Separator */}
          {!collapsed && (
            <div className="my-2 mx-3 border-t border-hairline-on-dark/50" />
          )}

          {/* Bottom nav items */}
          {bottomNavItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-primary/10 text-primary border-l-2 border-primary'
                    : 'text-muted hover:bg-surface-card-dark hover:text-body border-l-2 border-transparent'
                }`
              }
            >
              <span className="w-5 text-center shrink-0"><item.icon size={16} /></span>
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="p-3 border-t border-hairline-on-dark shrink-0 space-y-1">
          <button
            onClick={toggleTheme}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-md text-sm text-muted hover:bg-surface-card-dark hover:text-body transition-colors cursor-pointer"
          >
            <span className="w-5 text-center shrink-0">{theme === 'dark' ? <FiSun size={16} /> : <FiMoon size={16} />}</span>
            {!collapsed && <span>{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>}
          </button>
          <button
            onClick={logout}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-md text-sm text-muted hover:bg-surface-card-dark hover:text-trading-down transition-colors cursor-pointer"
          >
            <span className="w-5 text-center shrink-0"><FiLogOut size={16} /></span>
            {!collapsed && <span>Logout</span>}
          </button>
        </div>
      </aside>

      <main className={`flex-1 overflow-y-auto bg-canvas-dark pt-[52px] md:pt-0`}>
        <Outlet />
      </main>
    </div>
  )
}

function BotChip({
  bot,
  isActive,
  onClick,
  size = 'sm',
}: {
  bot: Bot
  isActive: boolean
  onClick: () => void
  size?: 'sm' | 'md'
}) {
  const live = isBotLive(bot)
  const color = STRATEGY_COLORS[bot.strategy_type] ?? '#707a8a'
  const label = size === 'sm' ? bot.name : `${bot.name} (${bot.strategy_type})`

  return (
    <button
      onClick={onClick}
      className={`
        inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono transition-colors cursor-pointer
        ${isActive
          ? 'bg-surface-elevated-dark text-body'
          : 'text-muted hover:text-body hover:bg-surface-elevated-dark/50'}
        ${size === 'md' ? 'text-xs' : 'text-[10px]'}
      `}
    >
      <span
        className="inline-block w-1.5 h-1.5 rounded-full shrink-0"
        style={{ backgroundColor: color, boxShadow: live ? `0 0 4px ${color}` : undefined }}
      />
      {label}
      {live && <span className="w-1.5 h-1.5 rounded-full bg-trading-up inline-block" />}
    </button>
  )
}
