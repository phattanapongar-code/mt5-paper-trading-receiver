import { useState, useEffect, useCallback, useMemo } from 'react'
import client, { clearCache } from '../api/client'
import { useToast } from '../components/Toast'
import type { TraderHealth, TraderAccount, TraderPositionsResponse, TraderPosition, TradeResult, TraderSymbolInfo } from '../types/api'

type OrderSide = 'buy' | 'sell'

export default function LiveTrade() {
  const { addToast } = useToast()
  const [health, setHealth] = useState<TraderHealth | null>(null)
  const [account, setAccount] = useState<TraderAccount | null>(null)
  const [positions, setPositions] = useState<TraderPosition[]>([])
  const [availableSymbols, setAvailableSymbols] = useState<TraderSymbolInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const [form, setForm] = useState({
    symbol: 'XAUUSD',
    side: 'buy' as OrderSide,
    volume: 0.1,
    sl_pips: '',
    tp_pips: '',
    sl_price: '',
    tp_price: '',
  })

  const [pendingForm, setPendingForm] = useState({
    symbol: 'XAUUSD',
    pendingType: 'buy_limit' as string,
    volume: 0.1,
    price: '',
    sl_pips: '',
    tp_pips: '',
    sl_price: '',
    tp_price: '',
  })

  const pendingTypeOptions = [
    { value: 'buy_limit', label: 'Buy Limit' },
    { value: 'sell_limit', label: 'Sell Limit' },
    { value: 'buy_stop', label: 'Buy Stop' },
    { value: 'sell_stop', label: 'Sell Stop' },
  ]

  const [modifyForm, setModifyForm] = useState<{ ticket: number; sl: string; tp: string } | null>(null)

  useEffect(() => {
    setPendingForm(f => ({ ...f, symbol: form.symbol }))
  }, [form.symbol])

  const selectedSymbolInfo = useMemo(
    () => availableSymbols.find(s => s.symbol === form.symbol) ?? null,
    [form.symbol, availableSymbols],
  )

  const clampedVolume = useMemo(() => {
    if (!selectedSymbolInfo) return form.volume
    const step = selectedSymbolInfo.volume_step
    const v = Math.max(selectedSymbolInfo.volume_min, Math.min(selectedSymbolInfo.volume_max, form.volume))
    return Math.round(v / step) * step
  }, [form.volume, selectedSymbolInfo])

  const volumeWarning = useMemo(() => {
    if (!selectedSymbolInfo) return null
    if (form.volume < selectedSymbolInfo.volume_min) return `Min volume: ${selectedSymbolInfo.volume_min}`
    if (form.volume > selectedSymbolInfo.volume_max) return `Max volume: ${selectedSymbolInfo.volume_max}`
    return null
  }, [form.volume, selectedSymbolInfo])

  const fetchAll = useCallback(async () => {
    try {
      const [h, a, p, sym] = await Promise.all([
        client.get<TraderHealth>('/trader/health'),
        client.get<TraderAccount>('/trader/account'),
        client.get<TraderPositionsResponse>('/trader/positions'),
        client.get('/trader/symbols/available'),
      ])
      setHealth(h.data)
      setAccount(a.data)
      setPositions(p.data.positions ?? [])
      if (sym.data?.success) {
        setAvailableSymbols(sym.data.data)
        if (sym.data.data.length > 0 && !sym.data.data.some(s => s.symbol === form.symbol)) {
          setForm(f => ({ ...f, symbol: sym.data.data[0].symbol }))
        }
      }
      setError(null)
    } catch (err: any) {
      const msg = err?.response?.data?.error || err?.message || 'Connection failed'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 3000)
    return () => clearInterval(interval)
  }, [fetchAll])

  const handleOpen = useCallback(async (side: OrderSide) => {
    setSubmitting(true)
    try {
      const body: any = {
        symbol: form.symbol,
        type: side,
        volume: clampedVolume,
      }
      if (form.sl_pips) body.sl_pips = parseFloat(form.sl_pips)
      if (form.tp_pips) body.tp_pips = parseFloat(form.tp_pips)
      if (form.sl_price) body.sl = parseFloat(form.sl_price)
      if (form.tp_price) body.tp = parseFloat(form.tp_price)

      const res = await client.post<TradeResult>('/trader/open', body)
      if (res.data.ok) {
        addToast(`Order filled: ticket #${res.data.ticket}`, 'success')
        clearCache()
        fetchAll()
      } else {
        addToast(`Order failed: ${res.data.error}`, 'error')
      }
    } catch (err: any) {
      addToast('Open failed: ' + (err?.response?.data?.error || err.message), 'error')
    } finally {
      setSubmitting(false)
    }
  }, [form, clampedVolume, fetchAll, addToast])

  const handlePending = useCallback(async () => {
    setSubmitting(true)
    try {
      const body: any = {
        symbol: pendingForm.symbol,
        type: pendingForm.pendingType,
        volume: parseFloat(pendingForm.volume.toFixed(2)),
        price: parseFloat(pendingForm.price),
      }
      if (pendingForm.sl_pips) body.sl_pips = parseFloat(pendingForm.sl_pips)
      if (pendingForm.tp_pips) body.tp_pips = parseFloat(pendingForm.tp_pips)
      if (pendingForm.sl_price) body.sl = parseFloat(pendingForm.sl_price)
      if (pendingForm.tp_price) body.tp = parseFloat(pendingForm.tp_price)

      const res = await client.post<TradeResult>('/trader/pending', body)
      if (res.data.ok) {
        addToast(`Pending order placed: ticket #${res.data.ticket}`, 'success')
        clearCache()
        setPendingForm(f => ({ ...f, price: '' }))
      } else {
        addToast(`Pending order failed: ${res.data.error}`, 'error')
      }
    } catch (err: any) {
      addToast('Pending failed: ' + (err?.response?.data?.error || err.message), 'error')
    } finally {
      setSubmitting(false)
    }
  }, [pendingForm, fetchAll, addToast])

  const handleClose = useCallback(async (ticket?: number) => {
    setSubmitting(true)
    try {
      const body = ticket ? { ticket } : {}
      const res = await client.post<TradeResult>('/trader/close', body)
      if (res.data.ok) {
        addToast(`Position${ticket ? ` #${ticket}` : ''} closed`, 'success')
        clearCache()
        fetchAll()
      } else {
        addToast(`Close failed: ${res.data.error}`, 'error')
      }
    } catch (err: any) {
      addToast('Close failed: ' + (err?.response?.data?.error || err.message), 'error')
    } finally {
      setSubmitting(false)
    }
  }, [fetchAll, addToast])

  const handleCloseAll = useCallback(async () => {
    setSubmitting(true)
    try {
      const res = await client.post<TradeResult>('/trader/close_all')
      if (res.data.ok) {
        addToast('All positions closed', 'success')
        clearCache()
        fetchAll()
      }
    } catch (err: any) {
      addToast('Close all failed: ' + (err?.response?.data?.error || err.message), 'error')
    } finally {
      setSubmitting(false)
    }
  }, [fetchAll, addToast])

  const handleModify = useCallback(async (ticket: number) => {
    if (!modifyForm || modifyForm.ticket !== ticket) return
    setSubmitting(true)
    try {
      const body: any = { ticket }
      if (modifyForm.sl) body.sl = parseFloat(modifyForm.sl)
      if (modifyForm.tp) body.tp = parseFloat(modifyForm.tp)
      const res = await client.post<TradeResult>('/trader/modify', body)
      if (res.data.ok) {
        addToast(`Position #${ticket} modified`, 'success')
        setModifyForm(null)
        clearCache()
        fetchAll()
      } else {
        addToast(`Modify failed: ${res.data.error}`, 'error')
      }
    } catch (err: any) {
      addToast('Modify failed: ' + (err?.response?.data?.error || err.message), 'error')
    } finally {
      setSubmitting(false)
    }
  }, [modifyForm, fetchAll, addToast])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-muted text-sm font-mono">Loading...</div>
      </div>
    )
  }

  const connected = health?.connected ?? false
  const accountData = account ?? health?.account

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-body flex items-center gap-2">
          Live Trading
          {connected && <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-trading-up"><span className="w-1.5 h-1.5 rounded-full bg-trading-up shadow-[0_0_4px_#0ecb81] animate-pulse" />CONNECTED</span>}
          {!connected && <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-trading-down"><span className="w-1.5 h-1.5 rounded-full bg-trading-down shadow-[0_0_4px_#f6465d]" />DISCONNECTED</span>}
          {availableSymbols.length > 0 && (
            <span className="text-[10px] text-muted font-mono bg-surface-elevated-dark px-1.5 py-0.5 rounded">{availableSymbols.length} symbols</span>
          )}
        </h1>
        {account?.currency && (
          <span className="text-xs text-muted font-mono">{account.name} | {account.server}</span>
        )}
      </div>

      {error && (
        <div className="bg-trading-down/10 border border-trading-down/50 rounded-lg p-3 text-sm text-trading-down">
          {error} — <button onClick={fetchAll} className="underline cursor-pointer">Retry</button>
        </div>
      )}

      {accountData && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          <AccountCard label="Balance" value={accountData.balance} currency={accountData.currency} accent="trading-up" />
          <AccountCard label="Equity" value={accountData.equity} currency={accountData.currency} accent="trading-up" />
          <AccountCard label="Margin" value={accountData.margin} currency={accountData.currency} accent="trading-down" />
          <AccountCard label="Free Margin" value={accountData.margin_free} currency={accountData.currency} accent="primary" />
          <AccountCard label="Margin Level" value={accountData.margin_level} suffix="%" accent={accountData.margin_level > 100 ? 'trading-up' : 'trading-down'} />
          <AccountCard label="Leverage" value={`1:${accountData.leverage}`} accent="primary" />
        </div>
      )}

      <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
        <h2 className="text-sm font-semibold text-body mb-3">Quick Order</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
          <div>
            <label className="block text-xs text-muted mb-1">Symbol</label>
            <div className="flex items-center gap-2">
              <select value={form.symbol} onChange={e => setForm({ ...form, symbol: e.target.value })}
                className="flex-1 px-2 py-1.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body outline-none">
                {availableSymbols.map(s => (
                  <option key={s.symbol} value={s.symbol}>
                    {s.symbol}
                  </option>
                ))}
              </select>
              {selectedSymbolInfo && (
                <span className="text-[10px] text-muted font-mono whitespace-nowrap">
                  {selectedSymbolInfo.digits} dig
                </span>
              )}
            </div>
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Volume (lot)</label>
            <div className="flex items-center gap-2">
              <input type="number" step="0.01" min="0.01" value={form.volume}
                onChange={e => setForm({ ...form, volume: parseFloat(e.target.value) || 0.01 })}
                className="flex-1 px-2 py-1.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body outline-none" />
              {selectedSymbolInfo && (
                <span className="text-[10px] text-muted font-mono whitespace-nowrap">
                  {selectedSymbolInfo.volume_min}–{selectedSymbolInfo.volume_max}
                </span>
              )}
            </div>
            {volumeWarning && (
              <p className="text-[10px] text-trading-down mt-0.5">{volumeWarning}</p>
            )}
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">SL (pips)</label>
            <input type="number" step="1" placeholder="Optional" value={form.sl_pips}
              onChange={e => setForm({ ...form, sl_pips: e.target.value })}
              className="w-full px-2 py-1.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body outline-none" />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">TP (pips)</label>
            <input type="number" step="1" placeholder="Optional" value={form.tp_pips}
              onChange={e => setForm({ ...form, tp_pips: e.target.value })}
              className="w-full px-2 py-1.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body outline-none" />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
          <div>
            <label className="block text-xs text-muted mb-1">SL (price)</label>
            <input type="number" step="0.01" placeholder="Optional" value={form.sl_price}
              onChange={e => setForm({ ...form, sl_price: e.target.value })}
              className="w-full px-2 py-1.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body outline-none" />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">TP (price)</label>
            <input type="number" step="0.01" placeholder="Optional" value={form.tp_price}
              onChange={e => setForm({ ...form, tp_price: e.target.value })}
              className="w-full px-2 py-1.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body outline-none" />
          </div>
        </div>
        <div className="flex gap-3">
          <button disabled={submitting || !connected}
            onClick={() => handleOpen('buy')}
            className="flex-1 py-2 bg-trading-up/10 border border-trading-up/50 text-trading-up rounded-md text-sm font-semibold disabled:opacity-50 transition-colors cursor-pointer hover:bg-trading-up/20">
            BUY {form.symbol}
          </button>
          <button disabled={submitting || !connected}
            onClick={() => handleOpen('sell')}
            className="flex-1 py-2 bg-trading-down/10 border border-trading-down/50 text-trading-down rounded-md text-sm font-semibold disabled:opacity-50 transition-colors cursor-pointer hover:bg-trading-down/20">
            SELL {form.symbol}
          </button>
        </div>
        {selectedSymbolInfo && (
          <div className="mt-2 flex gap-3 text-[10px] text-muted font-mono">
            <span>Point: {selectedSymbolInfo.point}</span>
            <span>Contract: {selectedSymbolInfo.contract_size}</span>
            <span>Step: {selectedSymbolInfo.volume_step}</span>
          </div>
        )}
      </section>

      <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
        <h2 className="text-sm font-semibold text-body mb-3">Pending Order</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
          <div>
            <label className="block text-xs text-muted mb-1">Type</label>
            <select value={pendingForm.pendingType}
              onChange={e => setPendingForm({ ...pendingForm, pendingType: e.target.value })}
              className="w-full px-2 py-1.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body outline-none">
              {pendingTypeOptions.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Symbol</label>
            <select value={pendingForm.symbol}
              onChange={e => setPendingForm({ ...pendingForm, symbol: e.target.value })}
              className="w-full px-2 py-1.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body outline-none">
              {availableSymbols.map(s => (
                <option key={s.symbol} value={s.symbol}>{s.symbol}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Volume (lot)</label>
            <input type="number" step="0.01" min="0.01" value={pendingForm.volume}
              onChange={e => setPendingForm({ ...pendingForm, volume: parseFloat(e.target.value) || 0.01 })}
              className="w-full px-2 py-1.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body outline-none" />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Price</label>
            <input type="number" step="0.01" placeholder="Required" value={pendingForm.price}
              onChange={e => setPendingForm({ ...pendingForm, price: e.target.value })}
              className="w-full px-2 py-1.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body outline-none" />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
          <div>
            <label className="block text-xs text-muted mb-1">SL (pips)</label>
            <input type="number" step="1" placeholder="Optional" value={pendingForm.sl_pips}
              onChange={e => setPendingForm({ ...pendingForm, sl_pips: e.target.value })}
              className="w-full px-2 py-1.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body outline-none" />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">TP (pips)</label>
            <input type="number" step="1" placeholder="Optional" value={pendingForm.tp_pips}
              onChange={e => setPendingForm({ ...pendingForm, tp_pips: e.target.value })}
              className="w-full px-2 py-1.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body outline-none" />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">SL (price)</label>
            <input type="number" step="0.01" placeholder="Optional" value={pendingForm.sl_price}
              onChange={e => setPendingForm({ ...pendingForm, sl_price: e.target.value })}
              className="w-full px-2 py-1.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body outline-none" />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">TP (price)</label>
            <input type="number" step="0.01" placeholder="Optional" value={pendingForm.tp_price}
              onChange={e => setPendingForm({ ...pendingForm, tp_price: e.target.value })}
              className="w-full px-2 py-1.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body outline-none" />
          </div>
        </div>
        <button disabled={submitting || !connected || !pendingForm.price}
          onClick={handlePending}
          className="w-full py-2 bg-primary/10 border border-primary/50 text-primary rounded-md text-sm font-semibold disabled:opacity-50 transition-colors cursor-pointer hover:bg-primary/20">
          Place {pendingForm.pendingType.replace('_', ' ').toUpperCase()} {pendingForm.symbol}
        </button>
      </section>

      <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-body">Open Positions ({positions.length})</h2>
          {positions.length > 0 && (
            <button onClick={handleCloseAll} disabled={submitting}
              className="text-xs px-2 py-1 bg-trading-down/10 border border-trading-down/50 text-trading-down rounded disabled:opacity-50 cursor-pointer hover:bg-trading-down/20">
              Close All
            </button>
          )}
        </div>
        {positions.length === 0 ? (
          <p className="text-sm text-muted py-4 text-center">No open positions</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline-on-dark text-muted text-xs">
                  <th className="text-left p-2 font-medium">Ticket</th>
                  <th className="text-left p-2 font-medium">Symbol</th>
                  <th className="text-left p-2 font-medium">Type</th>
                  <th className="text-right p-2 font-medium">Vol</th>
                  <th className="text-right p-2 font-medium">Open</th>
                  <th className="text-right p-2 font-medium">SL</th>
                  <th className="text-right p-2 font-medium">TP</th>
                  <th className="text-right p-2 font-medium">Profit</th>
                  <th className="text-center p-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {positions.map(p => (
                  <tr key={p.ticket} className="border-b border-surface-elevated-dark hover:bg-surface-card-dark/50">
                    <td className="p-2 font-mono text-xs">{p.ticket}</td>
                    <td className="p-2 font-mono text-xs">{p.symbol}</td>
                    <td className="p-2"><span className={`text-xs font-semibold ${p.type === 'buy' ? 'text-trading-up' : 'text-trading-down'}`}>{p.type.toUpperCase()}</span></td>
                    <td className="p-2 font-mono text-xs text-right">{p.volume}</td>
                    <td className="p-2 font-mono text-xs text-right">{p.open_price.toFixed(2)}</td>
                    <td className="p-2 font-mono text-xs text-right">{p.sl?.toFixed(2) ?? '—'}</td>
                    <td className="p-2 font-mono text-xs text-right">{p.tp?.toFixed(2) ?? '—'}</td>
                    <td className={`p-2 font-mono text-xs text-right ${p.profit >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>
                      {p.profit >= 0 ? '+' : ''}{p.profit.toFixed(2)}
                    </td>
                    <td className="p-2 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <button onClick={() => setModifyForm(modifyForm?.ticket === p.ticket ? null : { ticket: p.ticket, sl: '', tp: '' })}
                          className="text-[10px] px-1.5 py-0.5 bg-primary/10 text-primary border border-primary/30 rounded cursor-pointer hover:bg-primary/20">
                          SL/TP
                        </button>
                        <button onClick={() => handleClose(p.ticket)} disabled={submitting}
                          className="text-[10px] px-1.5 py-0.5 bg-trading-down/10 text-trading-down border border-trading-down/30 rounded cursor-pointer hover:bg-trading-down/20">
                          Close
                        </button>
                      </div>
                      {modifyForm?.ticket === p.ticket && (
                        <div className="mt-2 flex items-center gap-2 justify-center">
                          <input type="number" step="0.01" placeholder="SL" value={modifyForm.sl}
                            onChange={e => setModifyForm({ ...modifyForm, sl: e.target.value })}
                            className="w-20 px-1 py-0.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-[10px] text-body outline-none" />
                          <input type="number" step="0.01" placeholder="TP" value={modifyForm.tp}
                            onChange={e => setModifyForm({ ...modifyForm, tp: e.target.value })}
                            className="w-20 px-1 py-0.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-[10px] text-body outline-none" />
                          <button onClick={() => handleModify(p.ticket)} disabled={submitting}
                            className="text-[10px] px-1.5 py-0.5 bg-primary/10 text-primary border border-primary/30 rounded cursor-pointer hover:bg-primary/20">
                            Update
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {health && (
        <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">Terminal</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div><span className="text-muted">Terminal: </span><span className="font-mono">{health.terminal ?? '—'} v{health.terminal_version ?? '?'}</span></div>
            <div><span className="text-muted">Symbols: </span><span className="font-mono">{(health.symbols ?? []).join(', ') || '—'}</span></div>
            <div><span className="text-muted">Queue: </span><span className="font-mono">{health.queue_size ?? 0}</span></div>
            <div><span className="text-muted">Status: </span><span className={`font-mono ${connected ? 'text-trading-up' : 'text-trading-down'}`}>{connected ? 'Online' : 'Offline'}</span></div>
          </div>
        </section>
      )}
    </div>
  )
}

function AccountCard({ label, value, currency, suffix, accent }: {
  label: string; value: number | string | null; currency?: string; suffix?: string; accent: string
}) {
  const accentMap: Record<string, string> = {
    'trading-up': 'text-trading-up border-trading-up/30',
    'trading-down': 'text-trading-down border-trading-down/30',
    'primary': 'text-primary border-primary/30',
    'muted': 'text-muted border-hairline-on-dark',
  }
  const displayValue = value != null
    ? (typeof value === 'number' ? `${value >= 0 ? '' : ''}${value.toFixed(2)}${currency ? ' ' + currency : ''}${suffix ?? ''}` : String(value))
    : '—'
  return (
    <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-3">
      <p className="text-[10px] text-muted mb-0.5">{label}</p>
      <p className={`font-mono text-sm font-semibold ${accentMap[accent]?.split(' ')[0] ?? 'text-body'}`}>{displayValue}</p>
    </div>
  )
}
