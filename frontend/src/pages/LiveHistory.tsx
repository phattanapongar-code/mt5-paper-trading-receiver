import { useState, useEffect, useCallback } from 'react'
import client from '../api/client'
import type { TraderPosition } from '../types/api'

export default function LiveHistory() {
  const [history, setHistory] = useState<TraderPosition[]>([])
  const [loading, setLoading] = useState(true)

  const fetchHistory = useCallback(async () => {
    try {
      const res = await client.get('/trader/history')
      setHistory(res.data?.deals ?? [])
    } catch {
      // trader may not support /history yet
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchHistory()
  }, [fetchHistory])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-muted text-sm font-mono">Loading...</div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-semibold text-body">Live Trade History</h1>

      {history.length === 0 ? (
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-8 text-center">
          <p className="text-sm text-muted">No trade history available</p>
          <p className="text-xs text-muted mt-1">Trade history from MT5 terminal will appear here once available</p>
        </div>
      ) : (
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline-on-dark text-muted text-xs">
                <th className="text-left p-3 font-medium">Ticket</th>
                <th className="text-left p-3 font-medium">Symbol</th>
                <th className="text-left p-3 font-medium">Type</th>
                <th className="text-right p-3 font-medium">Volume</th>
                <th className="text-right p-3 font-medium">Open</th>
                <th className="text-right p-3 font-medium">Close</th>
                <th className="text-right p-3 font-medium">Profit</th>
                <th className="text-right p-3 font-medium">Commission</th>
                <th className="text-right p-3 font-medium">Swap</th>
              </tr>
            </thead>
            <tbody>
              {history.map((d) => (
                <tr key={d.ticket} className="border-b border-surface-elevated-dark hover:bg-surface-card-dark/50">
                  <td className="p-3 font-mono text-xs">{d.ticket}</td>
                  <td className="p-3 font-mono text-xs">{d.symbol}</td>
                  <td className="p-3">
                    <span className={`text-xs font-semibold ${d.type === 'buy' ? 'text-trading-up' : 'text-trading-down'}`}>
                      {d.type.toUpperCase()}
                    </span>
                  </td>
                  <td className="p-3 font-mono text-xs text-right">{d.volume}</td>
                  <td className="p-3 font-mono text-xs text-right">{d.open_price?.toFixed(2) ?? '—'}</td>
                  <td className="p-3 font-mono text-xs text-right">—</td>
                  <td className={`p-3 font-mono text-xs text-right ${d.profit >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>
                    {d.profit >= 0 ? '+' : ''}{d.profit?.toFixed(2) ?? '—'}
                  </td>
                  <td className="p-3 font-mono text-xs text-right">{d.commission?.toFixed(2) ?? '—'}</td>
                  <td className="p-3 font-mono text-xs text-right">{d.swap?.toFixed(2) ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
