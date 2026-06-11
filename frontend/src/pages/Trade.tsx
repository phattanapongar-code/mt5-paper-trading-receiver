import { useState, useEffect, useCallback } from 'react'
import client from '../api/client'
import type { PaperAccount } from '../types/api'

export default function Trade() {
  const [paper, setPaper] = useState<PaperAccount | null>(null)
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({
    side: 'buy',
    lot: 0.01,
    stop_loss: '',
    take_profit: '',
    note: 'manual',
  })

  const fetchData = useCallback(async () => {
    try {
      const res = await client.get<{ paper: PaperAccount }>('/state')
      setPaper(res.data.paper)
    } catch {
    } finally {
      setLoading(false)
    }
  }, [])

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

      await client.post('/paper/open', {
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
  }, [form, fetchData])

  const handleClose = useCallback(async () => {
    try {
      await client.post('/paper/close', { note: 'manual_close' })
      fetchData()
    } catch (err) {
      console.error('Close position failed:', err)
      alert('Failed to close position: ' + (err instanceof Error ? err.message : 'Unknown error'))
    }
  }, [fetchData])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-muted text-sm font-mono">Loading...</div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-semibold text-body">Manual Trading</h1>

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
            disabled={!!(paper?.open_position)}
            className="w-full py-2 bg-trading-up/10 border border-trading-up/50 text-trading-up rounded-md text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {paper?.open_position ? 'Position Already Open' : 'Open Position'}
          </button>
        </form>
      </section>

      {paper?.open_position && (
        <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <h2 className="text-sm font-semibold text-body mb-3">Current Position</h2>
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
              <span className="text-muted text-xs">PnL (unrealized)</span>
              <p className={`font-mono ${paper.open_position.status === 'open' ? (paper?.open_position.status === 'open' ? 'text-trading-up' : 'text-trading-down') : 'text-muted'}`}>
                {paper.open_position.status === 'open' ? '—' : '—'}
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
        <h2 className="text-sm font-semibold text-body mb-3">Account Status</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-muted text-xs">Balance</span>
            <p className="font-mono text-lg text-primary font-semibold">${paper?.balance.toFixed(2) ?? '—'}</p>
          </div>
          <div>
            <span className="text-muted text-xs">Equity</span>
            <p className="font-mono text-lg text-primary font-semibold">${paper?.equity.toFixed(2) ?? '—'}</p>
          </div>
          <div>
            <span className="text-muted text-xs">Realized PnL</span>
            <p className={`font-mono text-lg ${paper?.realized_pnl !== undefined ? (paper.realized_pnl >= 0 ? 'text-trading-up' : 'text-trading-down') : 'text-muted'}`}>
              {paper?.realized_pnl !== undefined ? (paper.realized_pnl >= 0 ? '+' : '') + `$${paper.realized_pnl.toFixed(2)}` : '—'}
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
