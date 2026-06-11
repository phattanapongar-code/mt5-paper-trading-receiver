import { useState, useEffect, useCallback } from 'react'
import client from '../api/client'
import { useWebSocket } from '../api/ws'
import type { AppState, Trade } from '../types/api'

export default function Overview() {
  const [state, setState] = useState<AppState | null>(null)
  const [trades, setTrades] = useState<Trade[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    try {
      const [stateRes, tradesRes] = await Promise.all([
        client.get<AppState>('/state'),
        client.get<Trade[]>('/trades', { params: { limit: 12 } }),
      ])
      setState(stateRes.data)
      setTrades(tradesRes.data)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 2000)
    return () => clearInterval(interval)
  }, [fetchData])

  useWebSocket('/ws/ticks', () => {
    fetchData()
  })

  if (loading && !state) {
    return (
      <div className="flex items-center justify-center h-full bg-canvas-dark">
        <div className="animate-pulse text-muted text-sm font-mono">Loading...</div>
      </div>
    )
  }

  const tick = state?.latest_tick
  const paper = state?.paper
  const health = state?.health
  const exec = state?.execution

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-body">Overview</h1>
        <div className="flex items-center gap-3 text-xs font-mono">
          <span className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${health?.sender_online ? 'bg-trading-up shadow-[0_0_6px_#0ecb81]' : 'bg-trading-down shadow-[0_0_6px_#f6465d]'}`} />
            {health?.sender_online ? 'ONLINE' : 'OFFLINE'}
          </span>
          <span className="text-muted">
            WS: {health?.websocket_clients ?? 0}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card label="Bid" value={tick?.bid?.toFixed(2) ?? '—'} accent="primary" />
        <Card label="Ask" value={tick?.ask?.toFixed(2) ?? '—'} accent="primary" />
        <Card label="Spread" value={tick?.spread?.toFixed(1) ?? '—'} accent="primary" />
        <Card label="Last Seq" value={String(tick?.seq ?? '—')} accent="muted" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card
          label="Balance"
          value={paper?.balance != null ? `$${paper.balance.toFixed(2)}` : '—'}
          accent="trading-up"
        />
        <Card
          label="Equity"
          value={paper?.equity != null ? `$${paper.equity.toFixed(2)}` : '—'}
          accent="primary"
        />
        <Card
          label="Realized PnL"
          value={paper?.realized_pnl != null ? `${paper.realized_pnl >= 0 ? '+' : ''}$${paper.realized_pnl.toFixed(2)}` : '—'}
          accent={paper?.realized_pnl != null && paper.realized_pnl >= 0 ? 'trading-up' : 'trading-down'}
        />
        <Card
          label="Auto Execution"
          value={exec?.enabled ? 'ON' : 'OFF'}
          accent={exec?.enabled ? 'trading-up' : 'trading-down'}
        />
      </div>

      {paper?.open_position && (
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Open Position</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-muted text-xs">Side</span>
              <p className={`font-mono font-semibold ${paper.open_position.side === 'buy' ? 'text-trading-up' : 'text-trading-down'}`}>
                {paper.open_position.side.toUpperCase()}
              </p>
            </div>
            <div>
              <span className="text-muted text-xs">Lot</span>
              <p className="font-mono">{paper.open_position.lot}</p>
            </div>
            <div>
              <span className="text-muted text-xs">Entry</span>
              <p className="font-mono">{paper.open_position.entry.toFixed(2)}</p>
            </div>
            <div>
              <span className="text-muted text-xs">SL / TP</span>
              <p className="font-mono text-xs">
                {paper.open_position.stop_loss?.toFixed(2) ?? '—'} / {paper.open_position.take_profit?.toFixed(2) ?? '—'}
              </p>
            </div>
          </div>
        </div>
      )}

      {trades.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Recent Trades</h2>
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
                  <th className="text-left p-3 font-medium">Reason</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => (
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
                      {t.r_multiple != null ? t.r_multiple.toFixed(2) : '—'}
                    </td>
                    <td className="p-3 text-xs text-muted">{t.exit_reason ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function Card({ label, value, accent }: { label: string; value: string; accent: 'primary' | 'trading-up' | 'trading-down' | 'muted' }) {
  const accentMap = {
    primary: 'border-primary/30 text-primary',
    'trading-up': 'border-trading-up/30 text-trading-up',
    'trading-down': 'border-trading-down/30 text-trading-down',
    muted: 'border-hairline-on-dark text-muted',
  }
  return (
    <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
      <p className="text-xs text-muted mb-1">{label}</p>
      <p className={`font-mono text-lg font-semibold ${accentMap[accent]}`}>{value}</p>
    </div>
  )
}
