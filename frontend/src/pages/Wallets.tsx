import { useState, useEffect, useCallback } from 'react'
import client from '../api/client'
import type { Wallet, Bot } from '../types/api'

export default function Wallets() {
  const [wallets, setWallets] = useState<(Wallet & { botName?: string; bot_id?: number })[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    try {
      const [botsRes] = await Promise.all([
        client.get<Bot[]>('/bots'),
      ])
      const bots = botsRes.data
      const walletPromises = bots.map((bot) =>
        client.get<Wallet>(`/bots/${bot.id}/wallet`).then((r) => ({
          ...r.data,
          botName: bot.name,
          bot_id: bot.id,
          enabled: bot.enabled,
        })),
      )
      const results = await Promise.all(walletPromises)
      setWallets(results)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [])

  const resetWallet = useCallback(async (botId: number) => {
    const balance = prompt('New balance:')
    if (balance) {
      await client.post(`/bots/${botId}/wallet/reset`, { balance: parseFloat(balance) })
      fetchData()
    }
  }, [fetchData])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [fetchData])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-text-muted text-sm font-mono">Loading...</div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-semibold text-text-primary">Wallets</h1>

      {wallets.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {wallets.map((w) => (
            <div key={w.id} className="bg-surface-800 border border-surface-500 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-text-primary">{w.botName ?? `Bot #${w.bot_id!}`}</h2>
                <button
                  onClick={() => resetWallet(w.bot_id!)}
                  className="px-2 py-1 text-xs rounded bg-surface-700 text-text-muted hover:text-text-primary border border-surface-500 transition-colors cursor-pointer"
                >
                  Reset
                </button>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-text-muted">Balance</p>
                  <p className="font-mono text-sm text-cyber-cyan font-semibold">${w.balance.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-xs text-text-muted">Realized PnL</p>
                  <p className={`font-mono text-sm font-semibold ${w.realized_pnl >= 0 ? 'text-cyber-green' : 'text-cyber-red'}`}>
                    {w.realized_pnl >= 0 ? '+' : ''}${w.realized_pnl.toFixed(2)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-text-muted">Initial</p>
                  <p className="font-mono text-sm text-text-primary">${w.initial_balance.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-xs text-text-muted">Drawdown</p>
                  <p className={`font-mono text-sm ${w.max_drawdown > 0 ? 'text-cyber-red' : 'text-cyber-green'}`}>
                    {(w.max_drawdown * 100).toFixed(1)}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-text-muted">Peak Equity</p>
                  <p className="font-mono text-sm text-text-primary">${w.peak_equity.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-xs text-text-muted">Currency</p>
                  <p className="font-mono text-sm text-text-primary">{w.currency}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-surface-800 border border-surface-500 rounded-lg p-8 text-center">
          <p className="text-sm text-text-muted">No wallets found</p>
        </div>
      )}
    </div>
  )
}
