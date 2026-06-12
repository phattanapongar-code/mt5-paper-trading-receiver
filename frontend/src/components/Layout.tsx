import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useBotContext } from '../context/BotContext'
import type { Bot } from '../types/api'

const navItems = [
  { to: '/', label: 'Overview', icon: '◉' },
  { to: '/charts', label: 'Charts', icon: '▤' },
  { to: '/bots', label: 'Bots', icon: '◈' },
  { to: '/compare', label: 'Compare', icon: '⇄' },
  { to: '/trades', label: 'Trade History', icon: '≡' },
  { to: '/trade', label: 'Manual Trade', icon: '▲' },
  { to: '/signals', label: 'Signals', icon: '⚡' },
  { to: '/performance', label: 'Performance', icon: '◐' },
  { to: '/market-structure', label: 'Structure', icon: '◈' },
  { to: '/pending-orders', label: 'Pending', icon: '◷' },
  { to: '/settings', label: 'Settings', icon: '⚙' },
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
  const { allBots, selectedBot, setSelectedBot } = useBotContext()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden">
      <aside
        className={`flex flex-col bg-surface-card-dark border-r border-hairline-on-dark transition-all duration-200 ${
          collapsed ? 'w-16' : 'w-56'
        }`}
      >
        <div className="flex items-center gap-2 h-13 px-4 border-b border-hairline-on-dark shrink-0">
          {!collapsed && (
            <span className="font-sans text-xs tracking-widest text-primary font-bold uppercase">
              PAPER TRADING
            </span>
          )}
          {collapsed && selectedBot && (
            <span className="text-primary font-mono text-sm font-semibold truncate" title={selectedBot.name}>
              {selectedBot.name.slice(0, 2).toUpperCase()}
            </span>
          )}
          {!collapsed && !selectedBot && (
            <span className="text-xs text-muted font-mono ml-0.5">All</span>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="ml-auto text-muted hover:text-body cursor-pointer text-lg leading-none"
          >
            {collapsed ? '▸' : '◂'}
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

        <nav className="flex-1 overflow-y-auto py-2 px-1 space-y-0.5">
          {navItems.map((item) => (
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
              <span className="w-5 text-center text-base shrink-0">{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="p-3 border-t border-hairline-on-dark shrink-0">
          <button
            onClick={logout}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-md text-sm text-muted hover:bg-surface-card-dark hover:text-trading-down transition-colors cursor-pointer"
          >
            <span className="w-5 text-center shrink-0">↩</span>
            {!collapsed && <span>Logout</span>}
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto bg-canvas-dark">
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
      {live && <span className="text-trading-up">●</span>}
    </button>
  )
}
