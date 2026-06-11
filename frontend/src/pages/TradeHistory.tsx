import { useState, useEffect, useCallback, useMemo } from 'react'
import client from '../api/client'
import type { Trade, Stats } from '../types/api'

export default function TradeHistory() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [sideFilter, setSideFilter] = useState('all')
  const [dateFilter, setDateFilter] = useState('all')

  const fetchData = useCallback(async () => {
    try {
      const [tradesRes, statsRes] = await Promise.all([
        client.get<Trade[]>('/trades', { params: { limit: 500 } }),
        client.get<Stats>('/stats'),
      ])
      setTrades(tradesRes.data)
      setStats(statsRes.data)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const filteredTrades = useMemo(() => {
    let filtered = trades

    if (sideFilter !== 'all') {
      filtered = filtered.filter((t) => t.side === sideFilter)
    }

    if (dateFilter !== 'all') {
      const now = Date.now() / 1000
      const cutoff = dateFilter === 'today' ? now - 86400 : dateFilter === '7d' ? now - 7 * 86400 : dateFilter === '30d' ? now - 30 * 86400 : 0
      if (cutoff > 0) {
        filtered = filtered.filter((t) => (t.closed_at ?? t.opened_at) >= cutoff)
      }
    }

    return filtered.sort((a, b) => (b.closed_at ?? b.opened_at) - (a.closed_at ?? a.opened_at))
  }, [trades, sideFilter, dateFilter])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-muted text-sm font-mono">Loading...</div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-lg font-semibold text-body">Trade History</h1>
        <div className="flex gap-2">
          <select value={sideFilter} onChange={(e) => setSideFilter(e.target.value)}
            className="px-2 py-1.5 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded text-body focus:outline-none focus:border-primary">
            <option value="all">All Sides</option>
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
          <select value={dateFilter} onChange={(e) => setDateFilter(e.target.value)}
            className="px-2 py-1.5 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded text-body focus:outline-none focus:border-primary">
            <option value="all">All Time</option>
            <option value="today">Today</option>
            <option value="7d">7 Days</option>
            <option value="30d">30 Days</option>
          </select>
          <span className="text-xs text-muted font-mono self-center">{filteredTrades.length} trades</span>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Total Trades" value={stats.closed_trades} />
          <StatCard label="Win Rate" value={stats.win_rate != null ? `${(stats.win_rate * 100).toFixed(1)}%` : '—'} accent={stats.win_rate != null && stats.win_rate >= 0.5 ? 'trading-up' : 'trading-down'} />
          <StatCard label="Profit Factor" value={stats.profit_factor?.toFixed(2) ?? '—'} accent={stats.profit_factor != null && stats.profit_factor >= 1.5 ? 'trading-up' : stats.profit_factor != null && stats.profit_factor >= 1 ? 'primary' : 'trading-down'} />
          <StatCard label="Total PnL" value={`${(stats.net_pnl ?? 0) >= 0 ? '+' : ''}$${(stats.net_pnl ?? 0).toFixed(2)}`} accent={(stats.net_pnl ?? 0) >= 0 ? 'trading-up' : 'trading-down'} />
          <StatCard label="Winners" value={stats.wins} accent="trading-up" />
          <StatCard label="Losers" value={stats.losses} accent="trading-down" />
          <StatCard label="Max DD" value={stats.max_drawdown_usd != null ? `$${stats.max_drawdown_usd.toFixed(2)}` : '—'} accent="trading-down" />
          <StatCard label="Avg R" value={stats.average_r?.toFixed(2) ?? '—'} accent={stats.average_r != null && stats.average_r >= 0 ? 'trading-up' : 'trading-down'} />
        </div>
      )}

      {filteredTrades.length > 0 ? (
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline-on-dark text-muted text-xs">
                <th className="text-left p-3 font-medium">ID</th>
                <th className="text-left p-3 font-medium">Side</th>
                <th className="text-left p-3 font-medium">Lot</th>
                <th className="text-right p-3 font-medium">Entry</th>
                <th className="text-right p-3 font-medium">Exit</th>
                <th className="text-right p-3 font-medium">PnL</th>
                <th className="text-right p-3 font-medium">R</th>
                <th className="text-left p-3 font-medium">Exit Reason</th>
                <th className="text-left p-3 font-medium">Date</th>
              </tr>
            </thead>
            <tbody>
              {filteredTrades.map((t) => (
                <tr key={t.id} className="border-b border-surface-elevated-dark hover:bg-surface-card-dark/50">
                  <td className="p-3 font-mono text-xs">{t.id}</td>
                  <td className="p-3">
                    <span className={`text-xs font-semibold ${t.side === 'buy' ? 'text-trading-up' : 'text-trading-down'}`}>
                      {t.side.toUpperCase()}
                    </span>
                  </td>
                  <td className="p-3 font-mono text-xs">{t.lot}</td>
                  <td className="p-3 font-mono text-xs text-right">{t.entry.toFixed(2)}</td>
                  <td className="p-3 font-mono text-xs text-right">{t.exit?.toFixed(2) ?? '—'}</td>
                  <td className={`p-3 font-mono text-xs text-right ${t.pnl != null ? (t.pnl >= 0 ? 'text-trading-up' : 'text-trading-down') : ''}`}>
                    {t.pnl != null ? `${t.pnl >= 0 ? '+' : ''}$${t.pnl.toFixed(2)}` : '—'}
                  </td>
                  <td className={`p-3 font-mono text-xs text-right ${t.r_multiple != null ? (t.r_multiple >= 0 ? 'text-trading-up' : 'text-trading-down') : ''}`}>
                    {t.r_multiple?.toFixed(2) ?? '—'}
                  </td>
                  <td className="p-3 text-xs text-muted">{t.exit_reason ?? '—'}</td>
                  <td className="p-3 text-xs text-muted font-mono">
                    {t.closed_at ? new Date(t.closed_at * 1000).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-8 text-center">
          <p className="text-sm text-muted">No trades match the selected filters</p>
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value, accent = 'muted' }: { label: string; value: string | number; accent?: 'trading-up' | 'trading-down' | 'primary' | 'muted' }) {
  const colorMap = {
    'trading-up': 'text-trading-up',
    'trading-down': 'text-trading-down',
    primary: 'text-primary',
    muted: 'text-body',
  }
  return (
    <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
      <p className="text-xs text-muted mb-1">{label}</p>
      <p className={`font-mono text-lg font-semibold ${colorMap[accent]}`}>{value}</p>
    </div>
  )
}