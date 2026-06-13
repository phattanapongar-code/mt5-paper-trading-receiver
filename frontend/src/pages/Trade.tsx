import { useState, useEffect, useCallback, useMemo } from 'react'
import client from '../api/client'
import { useBotContext } from '../context/BotContext'
import { useToast } from '../components/Toast'
import { FiTriangle } from 'react-icons/fi'
import type { BotState, Wallet } from '../types/api'

export default function Trade() {
  const { selectedBot, allBots } = useBotContext()
  const [selectedBotId, setSelectedBotId] = useState<number | null>(selectedBot?.id ?? null)
  const [botState, setBotState] = useState<BotState | null>(null)
  const [wallet, setWallet] = useState<Wallet | null>(null)
  const [health, setHealth] = useState<{ latest_tick: { bid: number; ask: number } } | null>(null)
  const [loading, setLoading] = useState(true)
  const { addToast } = useToast()
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
    if (!selectedBotId) {
      setBotState(null)
      setWallet(null)
      setLoading(false)
      return
    }
    try {
      const [stateRes, walletRes, healthRes] = await Promise.all([
        client.get<BotState>(`/bots/${selectedBotId}/state`),
        client.get<Wallet>(`/bots/${selectedBotId}/wallet`),
        fetch('/health').then(r => r.json()),
      ])
      setBotState(stateRes.data)
      setWallet(walletRes.data)
      setHealth(healthRes as any)
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
    if (!selectedBotId) return
    try {
      const stopLoss = form.stop_loss ? parseFloat(form.stop_loss) : undefined
      const takeProfit = form.take_profit ? parseFloat(form.take_profit) : undefined

      const lot = parseFloat(form.lot.toFixed(2))
      await client.post(`/bots/${selectedBotId}/open`, {
        side: form.side,
        lot,
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
      addToast('Failed to open position: ' + (err instanceof Error ? err.message : 'Unknown error'), 'error')
    }
  }, [form, selectedBotId, fetchData])

  const handleClose = useCallback(async () => {
    if (!selectedBotId) return
    try {
      await client.post(`/bots/${selectedBotId}/close`, { note: 'manual_close' })
      fetchData()
    } catch (err) {
      addToast('Failed to close position: ' + (err instanceof Error ? err.message : 'Unknown error'), 'error')
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
            value={selectedBotId ?? ''}
            onChange={(e) => setSelectedBotId(e.target.value ? Number(e.target.value) : null)}
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
          {/* Position Sizing Calculator */}
          {form.stop_loss && health?.latest_tick && (
            <div className="bg-surface-elevated-dark/30 rounded p-3 text-xs space-y-1 mb-2">
              <p className="text-muted font-semibold mb-1 inline-flex items-center gap-1"><FiTriangle size={14} /> Position Sizing</p>
              {(() => {
                const entry = health.latest_tick?.bid ?? 0
                const sl = parseFloat(form.stop_loss)
                const riskDist = Math.abs(entry - sl)
                if (riskDist <= 0) return null
                const contractSize = 100
                const riskPercent = 0.01
                const riskUsd = balance * riskPercent
                const commissionPerLot = botState?.bot?.parameters?.commission_per_lot as number ?? 3.5
                const denom = riskDist * contractSize + commissionPerLot
                const suggestedLot = denom > 0 ? Math.floor((riskUsd / denom) / 0.01) * 0.01 : 0.01
                const minLot = 0.01, maxLot = 10.0
                const finalLot = Math.max(minLot, Math.min(maxLot, suggestedLot))
                const totalCommission = finalLot * commissionPerLot
                const netRisk = riskDist * finalLot * contractSize
                return (
                  <>
                    <div className="flex justify-between"><span className="text-muted">Entry</span><span className="font-mono">${entry.toFixed(2)}</span></div>
                    <div className="flex justify-between"><span className="text-muted">Risk Distance</span><span className="font-mono">${riskDist.toFixed(2)}</span></div>
                    <div className="flex justify-between"><span className="text-muted">Hard Risk ({riskPercent*100}%)</span><span className="font-mono text-trading-down">${riskUsd.toFixed(2)}</span></div>
                    <div className="flex justify-between"><span className="text-muted">Commission @ {commissionPerLot}/lot</span><span className="font-mono text-trading-down">-${totalCommission.toFixed(2)}</span></div>
                    <div className="flex justify-between"><span className="text-muted">Net Risk (SL)</span><span className="font-mono text-trading-down">${netRisk.toFixed(2)}</span></div>
                    <div className="border-t border-hairline-on-dark/50 pt-1 flex justify-between font-semibold">
                      <span>Suggested Lot</span>
                      <span className="font-mono text-primary">{finalLot.toFixed(2)}</span>
                    </div>
                  </>
                )
              })()}
            </div>
          )}          
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
                  onChange={(e) => setForm({ ...form, lot: e.target.value ? parseFloat(e.target.value) : 0.01 })}
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
        <h2 className="text-sm font-semibold text-body mb-3">
          Wallet — {allBots.find(b => b.id === selectedBotId)?.name ?? (selectedBotId ? `#${selectedBotId}` : 'None selected')}
        </h2>
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
