import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import client from '../api/client'
import { useToast } from '../components/Toast'
import { useBotContext } from '../context/BotContext'
import type { Trade } from '../types/api'

const fmtTime = (ts: number | null | undefined) => {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleString(undefined, {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  })
}

export default function TradeHistory() {
  const { selectedBot, allBots } = useBotContext()
  const { addToast } = useToast()
  const [trades, setTrades] = useState<Trade[]>([])
  const [loading, setLoading] = useState(true)
  const [sideFilter, setSideFilter] = useState('all')
  const [dateFilter, setDateFilter] = useState('all')
  const cancelledRef = useRef(false)

  const fetchData = useCallback(async () => {
    try {
      const params: Record<string, unknown> = { limit: 500 }
      if (selectedBot) params.bot_id = selectedBot.id

      const tradesRes = await client.get<Trade[]>('/trades', { params })
      if (!cancelledRef.current) setTrades(tradesRes.data)
    } catch {
      if (!cancelledRef.current) addToast('Failed to load trades', 'error')
    } finally {
      if (!cancelledRef.current) setLoading(false)
    }
  }, [selectedBot, addToast])

  useEffect(() => {
    cancelledRef.current = false
    fetchData()
    return () => { cancelledRef.current = true }
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

  const stats = useMemo(() => {
    const closed = filteredTrades.filter((t) => t.status === 'closed')
    const pnls = closed.map((t) => t.pnl ?? 0)
    const rs = closed.map((t) => t.r_multiple ?? 0).filter((r) => r !== 0)
    const wins = pnls.filter((p) => p > 0)
    const losses = pnls.filter((p) => p < 0)
    const grossProfit = wins.reduce((s, v) => s + v, 0)
    const grossLoss = Math.abs(losses.reduce((s, v) => s + v, 0))
    let maxDd = 0, peak = 0, cumulative = 0
    for (const p of pnls) {
      cumulative += p; peak = Math.max(peak, cumulative)
      maxDd = Math.max(maxDd, peak - cumulative)
    }
    const avgR = rs.length > 0 ? rs.reduce((s, v) => s + v, 0) / rs.length : 0
    return {
      closed_trades: closed.length,
      wins: wins.length,
      losses: losses.length,
      win_rate: closed.length > 0 ? wins.length / closed.length : 0,
      profit_factor: grossLoss > 0 ? grossProfit / grossLoss : null,
      net_pnl: pnls.reduce((s, v) => s + v, 0),
      max_drawdown_usd: maxDd,
      average_r: avgR,
    }
  }, [filteredTrades])

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
          <h1 className="text-lg font-semibold text-body">
            Trade History{selectedBot ? ` — ${selectedBot.name}` : ''}
          </h1>
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
          <button onClick={() => {
            const header = 'ID,Bot,Side,Lot,Entry,Exit,PnL,R-Multiple,Exit Reason,Opened,Closed'
            const rows = filteredTrades.map(t =>
              [t.id, t.bot_id ?? '', t.side, t.lot, t.entry, t.exit ?? '', t.pnl ?? '', t.r_multiple ?? '', t.exit_reason ?? '', fmtTime(t.opened_at), fmtTime(t.closed_at)].join(',')
            )
            const blob = new Blob(['\uFEFF' + header + '\n' + rows.join('\n')], { type: 'text/csv;charset=utf-8;' })
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a'); a.href = url; a.download = 'trades.csv'; a.click()
            URL.revokeObjectURL(url)
          }} className="px-3 py-1.5 text-xs rounded bg-primary/10 text-primary border border-primary/50 cursor-pointer">
            Export CSV
          </button>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Total Trades" value={stats.closed_trades} />
          <StatCard label="Win Rate" value={stats.win_rate != null ? `${(stats.win_rate * 100).toFixed(1)}%` : '—'} accent={stats.win_rate != null && stats.win_rate >= 0.5 ? 'trading-up' : 'trading-down'} />
          <StatCard label="Profit Factor" value={stats.profit_factor?.toFixed(2) ?? '—'} accent={stats.profit_factor != null && stats.profit_factor >= 1.5 ? 'trading-up' : stats.profit_factor != null && stats.profit_factor >= 1 ? 'primary' : 'trading-down'} />
          <StatCard label="Total PnL" value={`${stats.net_pnl >= 0 ? '+' : ''}$${stats.net_pnl.toFixed(2)}`} accent={stats.net_pnl >= 0 ? 'trading-up' : 'trading-down'} />
          <StatCard label="Winners" value={stats.wins} accent="trading-up" />
          <StatCard label="Losers" value={stats.losses} accent="trading-down" />
          <StatCard label="Max DD" value={`$${stats.max_drawdown_usd.toFixed(2)}`} accent="trading-down" />
          <StatCard label="Avg R" value={stats.average_r?.toFixed(2) ?? '—'} accent={stats.average_r != null && stats.average_r >= 0 ? 'trading-up' : 'trading-down'} />
        </div>
      )}

      {filteredTrades.length > 0 ? (
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline-on-dark text-muted text-xs">
                <th className="text-left p-3 font-medium">ID</th>
                <th className="text-left p-3 font-medium">Bot</th>
                <th className="text-left p-3 font-medium">Side</th>
                <th className="text-left p-3 font-medium">Lot</th>
                <th className="text-right p-3 font-medium">Entry</th>
                <th className="text-right p-3 font-medium">Exit</th>
                <th className="text-right p-3 font-medium">PnL</th>
                <th className="text-right p-3 font-medium">R</th>
                <th className="text-left p-3 font-medium">Exit Reason</th>
                <th className="text-left p-3 font-medium">Opened</th>
                <th className="text-left p-3 font-medium">Closed</th>
              </tr>
            </thead>
            <tbody>
              {filteredTrades.map((t) => (
                <tr key={t.id} className="border-b border-surface-elevated-dark hover:bg-surface-card-dark/50">
                  <td className="p-3 font-mono text-xs">{t.id}</td>
                  <td className="p-3 font-mono text-xs text-muted">
                    {allBots.find((b) => b.id === t.bot_id)?.name ?? `#${t.bot_id}`}
                  </td>
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
                  <td className="p-3 text-xs text-muted font-mono">{fmtTime(t.opened_at)}</td>
                  <td className="p-3 text-xs text-muted font-mono">{fmtTime(t.closed_at)}</td>
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
