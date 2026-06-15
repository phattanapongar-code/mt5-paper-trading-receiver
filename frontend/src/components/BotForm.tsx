import { useState, useEffect } from 'react'
import client from '../api/client'
import type { Profile, StrategyOption } from '../types/api'

const DEFAULT_SYMBOLS = ['XAUUSD', 'BTCUSD', 'ETHUSD', 'EURUSD', 'GBPUSD', 'USDCAD', 'USDJPY', 'AUDUSD', 'SPX500', 'NAS100']

interface Props {
  profiles: Profile[]
  onClose: () => void
  onCreated: () => void
}

export default function BotForm({ profiles, onClose, onCreated }: Props) {
  const [profileId, setProfileId] = useState(profiles[0]?.id ?? 0)
  const [name, setName] = useState('')
  const [symbol, setSymbol] = useState('XAUUSD')
  const [timeframe, setTimeframe] = useState('M15')
  const [strategyType, setStrategyType] = useState('trend_ob')
  const [strategies, setStrategies] = useState<StrategyOption[]>([])
  const [symbols, setSymbols] = useState<string[]>(DEFAULT_SYMBOLS)
  const [initialBalance, setInitialBalance] = useState('500')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    client.get<StrategyOption[]>('/strategies').then((res) => {
      setStrategies(res.data)
    }).catch(() => {})
    // Fetch available symbols from backend
    client.get<{ symbols: string[] }>('/symbols').then(res => {
      if (res.data.symbols?.length) setSymbols(res.data.symbols)
    }).catch(() => {})
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await client.post('/bots', {
        profile_id: profileId,
        name,
        symbol,
        timeframe,
        strategy_type: strategyType,
        initial_balance: parseFloat(initialBalance),
      })
      onCreated()
      onClose()
    } catch {
      alert('Failed to create bot')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-6 w-96" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-sm font-semibold text-body mb-4">Create Bot</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <select value={profileId} onChange={(e) => setProfileId(Number(e.target.value))}
            className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body focus:outline-none focus:border-primary">
            {profiles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <input type="text" placeholder="Bot name" value={name} onChange={(e) => setName(e.target.value)}
            className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body placeholder:text-muted focus:outline-none focus:border-primary" required autoFocus />
          <select value={symbol} onChange={(e) => setSymbol(e.target.value)}
            className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body focus:outline-none focus:border-primary">
            {symbols.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}
            className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body focus:outline-none focus:border-primary">
            <option value="M1">M1</option>
            <option value="M5">M5</option>
            <option value="M15">M15</option>
            <option value="H1">H1</option>
          </select>
          <select value={strategyType} onChange={(e) => setStrategyType(e.target.value)}
            className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body focus:outline-none focus:border-primary">
            {strategies.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          {strategies.find((s) => s.id === strategyType) && (
            <p className="text-xs text-muted">{strategies.find((s) => s.id === strategyType)!.description}</p>
          )}
          <input type="number" placeholder="Initial balance" value={initialBalance} onChange={(e) => setInitialBalance(e.target.value)}
            className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body placeholder:text-muted focus:outline-none focus:border-primary" min="1" step="0.01" />
          <div className="flex gap-2 justify-end pt-2">
            <button type="button" onClick={onClose} className="px-3 py-1.5 text-xs bg-surface-elevated-dark text-muted rounded border border-hairline-on-dark cursor-pointer">Cancel</button>
            <button type="submit" disabled={saving || !name} className="px-3 py-1.5 text-xs bg-primary/10 text-primary rounded border border-primary/50 disabled:opacity-40 cursor-pointer">{saving ? 'Saving...' : 'Create'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}
