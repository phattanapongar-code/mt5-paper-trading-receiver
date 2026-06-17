import { useState, useEffect } from 'react'
import client from '../api/client'
import type { BacktestHistory } from '../types/api'

export default function BacktestOptimize() {
  const [history, setHistory] = useState<BacktestHistory[]>([])

  useEffect(() => {
    client.get<BacktestHistory[]>('/backtest/history', { params: { limit: 20 } })
      .then(res => setHistory(res.data)).catch(() => {})
  }, [])

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-semibold text-body">Backtest History</h1>
      <p className="text-xs text-muted">
        Parameter optimizer is not available with visual strategy graphs.
        Use the Backtest page to run individual simulations.
      </p>

      {history.length > 0 ? (
        <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="border-b border-hairline-on-dark text-muted">
                <th className="text-left p-2">Symbol</th>
                <th className="text-right p-2">Trades</th><th className="text-right p-2">Net PnL</th>
                <th className="text-right p-2">Win Rate</th><th className="text-right p-2">PF</th>
                <th className="text-right p-2">Sharpe</th><th className="text-right p-2">DD</th>
              </tr></thead>
              <tbody>
                {history.map(h => (
                  <tr key={h.id} className="border-b border-surface-elevated-dark">
                    <td className="p-2 font-mono">{h.symbol} {h.timeframe}</td>
                    <td className="p-2 font-mono text-right">{h.total_trades}</td>
                    <td className={`p-2 font-mono text-right ${h.net_pnl >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>${h.net_pnl.toFixed(2)}</td>
                    <td className="p-2 font-mono text-right">{(h.win_rate * 100).toFixed(0)}%</td>
                    <td className="p-2 font-mono text-right">{h.profit_factor.toFixed(2)}</td>
                    <td className="p-2 font-mono text-right">{h.sharpe_ratio.toFixed(2)}</td>
                    <td className="p-2 font-mono text-right">{h.max_drawdown_pct.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <p className="text-sm text-muted">No backtest history yet.</p>
      )}
    </div>
  )
}
