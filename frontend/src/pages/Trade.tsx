import { useState, useEffect, useCallback, useMemo } from 'react'
import client from '../api/client'
import { useBotContext } from '../context/BotContext'
import type { BotState, Wallet } from '../types/api'

export default function Trade() {
  const { selectedBot, allBots } = useBotContext()
  const [selectedBotId, setSelectedBotId] = useState<number>(selectedBot?.id ?? 1)
  const [botState, setBotState] = useState<BotState | null>(null)
  const [wallet, setWallet] = useState<Wallet | null>(null)
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({
    side: 'buy',
    lot: 0.01,
    stop_loss: '',
    take_profit: '',
    note: 'manual',
  })

  useEffect(() => {
    if (selectedBot) setSelectedBotId(selectedBot.id)
  }, [selectedBot])

  const isFollowingSidebar = useMemo(
    () => selectedBot?.id === selectedBotId,
    [selectedBot, selectedBotId],
  )

  const fetchData = useCallback(async () => {
    try {
      const [stateRes, walletRes] = await Promise.all([
        client.get<BotState>(`/bots/${selectedBotId}/state`),
        client.get<Wallet>(`/bots/${selectedBotId}/wallet`),
      ])
      setBotState(stateRes.data)
      setWallet(walletRes.data)
    } catch {
    } finally {
      setLoading(false)
    }
  }, [selectedBotId])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 2000)
    return () => clearInterval(interval)
  }, [fetchData])

  const handleOpen = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const stopLoss = form.stop_loss ? parseFloat(form.stop_loss) : undefined
      const takeProfit = form.take_profit ? parseFloat(form.take_profit) : undefined

      await client.post(`/bots/${selectedBotId}/open`, {
        side: form.side,
        lot: parseFloat(form.lot.toFixed(2)),
        stop_loss: stopLoss,
        take_profit: takeProfit,
        note: form.note,
      })

      setForm({
        side: 'buy',
        lot: 0.01,
        stop_loss: '',
        take_profit: '',
        note: 'manual',
      })
      fetchData()
    } catch (err) {
      console.error('Open position failed:', err)
      alert('Failed to open position: ' + (err instanceof Error ? err.message : 'Unknown error'))
    }
  }, [form, selectedBotId, fetchData])

  const handleClose = useCallback(async () => {
    try {
      await client.post(`/bots/${selectedBotId}/close`, { note: 'manual_close' })
      fetchData()
    } catch (err) {
      console.error('Close position failed:', err)
      alert('Failed to close position: ' + (err instanceof Error ? err.message : 'Unknown error'))
    }
  }, [selectedBotId, fetchData])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-muted text-sm font-mono">Loading...</div>
      </div>
    )
  }

  const position = botState?.position ?? null
  const balance = wallet?.balance ?? 0
  const realizedPnl = wallet?.realized_pnl ?? 0

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-body">Manual Trading</h1>
        <div className="flex items-center gap-2">
          {!isFollowingSidebar && selectedBot && (
            <span className="text-[10px] text-primary/70 font-mono bg-primary/5 px-1.5 py-0.5 rounded">Override</span>
          )}
          <select
            value={selectedBotId}
            onChange={(e) => setSelectedBotId(Number(e.target.value))}
            className="px-2 py-1.5 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded text-body focus:outline-none focus:border-primary"
          >
            {allBots.map((b) => (
              <option key={b.id} value={b.id}>{b.name} (#{b.id})</option>
            ))}
          </select>
        </div>
      </div>

      <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
        <h2 className="text-sm font-semibold text-body mb-3">Open Position</h2>
        <form onSubmit={handleOpen} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-muted mb-1">Side</label>
              <select
                value={form.side}
                onChange={(e) => setForm({ ...form, side: e.target.value as 'buy' | 'sell' })}
                className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded-md text-sm text-body focus:outline-none focus:border-primary"
              >
                <option value="buy">BUY</option>
                <option value="sell">SELL</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-muted mb-1">Lot</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                max="10.0"
                value={form.lot}
                onChange={(e) => setForm({ ...form, lot: parseFloat(e.target.value) })}
                className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded-md text-sm text-body focus:outline-none focus:border-primary"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-muted mb-1">Stop Loss (price)</label>
              <input
                type="number"
                step="0.1"
                placeholder="Optional"
                value={form.stop_loss}
                onChange={(e) => setForm({ ...form, stop_loss: e.target.value })}
                className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded-md text-sm text-body focus:outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="block text-xs text-muted mb-1">Take Profit (price)</label>
              <input
                type="number"
                step="0.1"
                placeholder="Optional"
                value={form.take_profit}
                onChange={(e) => setForm({ ...form, take_profit: e.target.value })}
                className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded-md text-sm text-body focus:outline-none focus:border-primary"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Note</label>
            <input
              type="text"
              value={form.note}
              onChange={(e) => setForm({ ...form, note: e.target.value })}
              className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded-md text-sm text-body focus:outline-none focus:border-primary"
            />
          </div>
          <button
            type="submit"
            disabled={!!position}
            className="w-full py-2 bg-trading-up/10 border border-trading-up/50 text-trading-up rounded-md text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {position ? 'Position Already Open' : 'Open Position'}
          </button>
        </form>
      </section>

      {position && (
        <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <h2 className="text-sm font-semibold text-body mb-3">Current Position</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-muted text-xs">Side</span>
              <p className={`font-mono font-semibold ${position.side === 'buy' ? 'text-trading-up' : 'text-trading-down'}`}>
                {position.side.toUpperCase()}
              </p>
            </div>
            <div>
              <span className="text-muted text-xs">Lot</span>
              <p className="font-mono">{position.lot}</p>
            </div>
            <div>
              <span className="text-muted text-xs">Entry</span>
              <p className="font-mono">{position.entry.toFixed(2)}</p>
            </div>
            <div>
              <span className="text-muted text-xs">PnL (unrealized)</span>
              <p className={`font-mono ${(position.pnl ?? 0) >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>
                {(position.pnl ?? 0) >= 0 ? '+' : ''}${(position.pnl ?? 0).toFixed(2)}
              </p>
            </div>
          </div>
          <div className="mt-4">
            <button
              onClick={handleClose}
              className="w-full py-2 bg-trading-down/10 border border-trading-down/50 text-trading-down rounded-md text-sm font-semibold hover:bg-trading-down/20 transition-colors"
            >
              Close Position
            </button>
          </div>
        </section>
      )}

      <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
        <h2 className="text-sm font-semibold text-body mb-3">Wallet — {allBots.find(b => b.id === selectedBotId)?.name ?? `#${selectedBotId}`}</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-muted text-xs">Balance</span>
            <p className="font-mono text-lg text-primary font-semibold">${balance.toFixed(2)}</p>
          </div>
          <div>
            <span className="text-muted text-xs">Realized PnL</span>
            <p className={`font-mono text-lg font-semibold ${realizedPnl >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>
              {realizedPnl >= 0 ? '+' : ''}${realizedPnl.toFixed(2)}
            </p>
          </div>
          <div>
            <span className="text-muted text-xs">Trend</span>
            <p className="font-mono text-lg text-body">{botState?.runtime?.latest_trend ?? '—'}</p>
          </div>
          <div>
            <span className="text-muted text-xs">Bot Status</span>
            <p className={`font-mono text-lg ${botState?.bot?.enabled ? 'text-trading-up' : 'text-trading-down'}`}>
              {botState?.bot?.enabled ? 'ON' : 'OFF'}
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
