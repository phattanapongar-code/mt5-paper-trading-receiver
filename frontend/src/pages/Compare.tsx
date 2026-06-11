import { useEffect, useState } from 'react'
import client from '../api/client'
import type { CompareBot } from '../types/api'

export default function Compare() {
  const [data, setData] = useState<CompareBot[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    client.get<CompareBot[]>('/compare').then((r) => setData(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-muted text-xs p-6">Loading...</div>

  if (!data.length) return <div className="text-muted text-xs p-6">No bots to compare.</div>

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-sm font-semibold text-body">Compare Bots</h1>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted uppercase tracking-wider border-b border-hairline-on-dark">
              <th className="text-left py-2 pr-3">Bot</th>
              <th className="text-left py-2 pr-3">Strategy</th>
              <th className="text-right py-2 pr-3">Balance</th>
              <th className="text-right py-2 pr-3">PnL</th>
              <th className="text-right py-2 pr-3">Win Rate</th>
              <th className="text-right py-2 pr-3">Trades</th>
              <th className="text-right py-2 pr-3">Max DD</th>
            </tr>
          </thead>
          <tbody>
            {data.map((b) => (
              <tr key={b.bot_id} className="border-b border-surface-elevated-dark text-text-secondary">
                <td className="py-2 pr-3">{b.name}
                  <span className="ml-2 text-muted">{b.profile_name}</span>
                </td>
                <td className="py-2 pr-3">{b.strategy_type} {b.strategy_version}</td>
                <td className="text-right py-2 pr-3 font-mono">{b.balance.toFixed(2)}</td>
                <td className={`text-right py-2 pr-3 font-mono ${b.net_pnl >= 0 ? 'text-trading-up' : 'text-rose-500'}`}>
                  {b.net_pnl >= 0 ? '+' : ''}{b.net_pnl.toFixed(2)}
                </td>
                <td className="text-right py-2 pr-3 font-mono">{b.closed_trades > 0 ? `${(b.win_rate * 100).toFixed(1)}%` : '-'}</td>
                <td className="text-right py-2 pr-3 font-mono">{b.closed_trades}</td>
                <td className="text-right py-2 pr-3 font-mono text-rose-500">{b.max_drawdown.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
