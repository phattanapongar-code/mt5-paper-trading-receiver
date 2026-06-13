import { useState, useEffect, useCallback, useRef } from 'react'
import client from '../api/client'
import { useToast } from '../components/Toast'
import type { Health, HistoryStatus, Bot, AlertConfig as AlertConfigData } from '../types/api'

export default function Settings() {
  const { addToast } = useToast()
  const [health, setHealth] = useState<Health | null>(null)
  const [historyStatus, setHistoryStatus] = useState<HistoryStatus | null>(null)
  const [bots, setBots] = useState<Bot[]>([])
  const [loading, setLoading] = useState(true)
  const historyFileInputRef = useRef<HTMLInputElement>(null)
  const [alertCfg, setAlertCfg] = useState<AlertConfigData>({ bot_token: '', chat_id: '', enabled: false })
  const [alertLoading, setAlertLoading] = useState(false)

  const fetchData = useCallback(async () => {
    try {
      const [historyStatusRes, botsRes, alertRes] = await Promise.all([
        client.get<HistoryStatus>('/history/status'),
        client.get<Bot[]>('/bots'),
        client.get<AlertConfigData>('/alerts/config').catch(() => ({ data: { bot_token: '', chat_id: '', enabled: false } as AlertConfigData })),
      ])
      setBots(botsRes.data)
      setHistoryStatus(historyStatusRes.data)
      setAlertCfg(alertRes.data)
      try {
        const healthRes = await fetch('/health')
        if (healthRes.ok) setHealth(await healthRes.json())
      } catch {}
    } catch {
    } finally {
      setLoading(false)
    }
  }, [])

  const handleHistoryImport = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    try {
      const text = await file.text()
      const data = JSON.parse(text)

      if (!Array.isArray(data.candles) || data.candles.length === 0) {
        alert('Invalid file format: candles array missing or empty')
        return
      }

      await client.post('/history/import', {
        symbol: data.symbol || 'XAUUSD',
        timeframe: data.timeframe || 'M1',
        source: data.source || 'file_upload',
        offset_seconds: data.offset_seconds || 0,
        candles: data.candles,
      })

      alert('History imported successfully!')
      fetchData()

      if (historyFileInputRef.current) {
        historyFileInputRef.current.value = ''
      }
    } catch (err) {
      console.error('History import failed:', err)
      alert('Failed to import history: ' + (err instanceof Error ? err.message : 'Unknown error'))
    }
  }, [fetchData])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-muted text-sm font-mono">Loading...</div>
      </div>
    )
  }

  const enabledBots = bots.filter((b) => b.enabled)

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <h1 className="text-lg font-semibold text-body">Settings</h1>

      <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
        <h2 className="text-sm font-semibold text-body mb-1">System</h2>
        {health && (
          <div className="grid grid-cols-2 gap-3 text-xs mb-3">
            <div>
              <span className="text-muted">Sender Status: </span>
              <span className={`font-mono ${health.sender_online ? 'text-trading-up' : 'text-trading-down'}`}>
                {health.sender_online ? 'ONLINE' : 'OFFLINE'}
              </span>
            </div>
            <div>
              <span className="text-muted">WebSocket Clients: </span>
              <span className="font-mono text-body">{health.websocket_clients}</span>
            </div>
            <div>
              <span className="text-muted">Last Seq: </span>
              <span className="font-mono text-body">{health.last_seq ?? '—'}</span>
            </div>
            <div>
              <span className="text-muted">Last Tick: </span>
              <span className="font-mono text-body">
                {health.seconds_since_last_message != null ? `${health.seconds_since_last_message}s ago` : '—'}
              </span>
            </div>
          </div>
        )}
        <div className="flex items-center gap-3 text-xs text-muted">
          <span>{bots.length} bots total</span>
          <span>·</span>
          <span className="text-trading-up">{enabledBots.length} enabled</span>
        </div>
      </section>

      <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
        <h2 className="text-sm font-semibold text-body mb-1">History Import</h2>
        <p className="text-xs text-muted mb-3">Upload historical candle data from MT5 or other sources</p>
        <div className="flex items-center gap-3">
          <input
            ref={historyFileInputRef}
            type="file"
            accept=".json"
            onChange={handleHistoryImport}
            className="block w-full text-sm text-muted file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary/10 file:text-primary hover:file:bg-primary/20 cursor-pointer"
          />
        </div>
      </section>

      {historyStatus && historyStatus.latest_import && (
        <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <h2 className="text-sm font-semibold text-body mb-3">History Import Status</h2>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-muted">Source: </span>
              <span className="font-mono text-body">{historyStatus.latest_import.source}</span>
            </div>
            <div>
              <span className="text-muted">Timeframe: </span>
              <span className="font-mono text-body">{historyStatus.latest_import.timeframe}</span>
            </div>
            <div>
              <span className="text-muted">Offset: </span>
              <span className="font-mono text-body">{historyStatus.latest_import.offset_seconds}s</span>
            </div>
            <div>
              <span className="text-muted">Last Import: </span>
              <span className="font-mono text-body">{new Date(historyStatus.latest_import.created_at * 1000).toLocaleString()}</span>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-hairline-on-dark">
            <p className="text-xs text-muted mb-2">Candles Count (after rebuild):</p>
            <div className="grid grid-cols-4 gap-2">
              <div className="text-center">
                <span className="block text-sm font-mono text-primary">{historyStatus.closed_candles['M1'] ?? 0}</span>
                <span className="text-xs text-muted">M1</span>
              </div>
              <div className="text-center">
                <span className="block text-sm font-mono text-primary">{historyStatus.closed_candles['M5'] ?? 0}</span>
                <span className="text-xs text-muted">M5</span>
              </div>
              <div className="text-center">
                <span className="block text-sm font-mono text-primary">{historyStatus.closed_candles['M15'] ?? 0}</span>
                <span className="text-xs text-muted">M15</span>
              </div>
              <div className="text-center">
                <span className="block text-sm font-mono text-primary">{historyStatus.closed_candles['H1'] ?? 0}</span>
                <span className="text-xs text-muted">H1</span>
              </div>
            </div>
          </div>
        </section>
      )}

      <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
        <h2 className="text-sm font-semibold text-body mb-3">Telegram Alerts</h2>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-muted mb-1">Bot Token</label>
            <input type="password" value={alertCfg.bot_token}
              onChange={e => setAlertCfg(prev => ({ ...prev, bot_token: e.target.value }))}
              placeholder="123456:ABC..."
              className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body font-mono focus:outline-none focus:border-primary" />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Chat ID</label>
            <input value={alertCfg.chat_id}
              onChange={e => setAlertCfg(prev => ({ ...prev, chat_id: e.target.value }))}
              placeholder="-100123456789"
              className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body font-mono focus:outline-none focus:border-primary" />
          </div>
          <div className="flex items-center gap-3">
            <label className="text-xs text-muted">Enabled</label>
            <button onClick={() => setAlertCfg(prev => ({ ...prev, enabled: !prev.enabled }))}
              className={`w-10 h-5 rounded-full transition-colors cursor-pointer ${alertCfg.enabled ? 'bg-trading-up' : 'bg-surface-400'}`}>
              <span className={`block w-4 h-4 bg-white rounded-full transition-transform ${alertCfg.enabled ? 'translate-x-5' : 'translate-x-0.5'}`} />
            </button>
          </div>
          <div className="flex gap-2">
            <button onClick={async () => {
              setAlertLoading(true)
              try {
                await client.post('/alerts/config', alertCfg)
                addToast('Alert config saved', 'success')
              } catch { addToast('Failed to save', 'error') }
              finally { setAlertLoading(false) }
            }} disabled={alertLoading}
              className="px-3 py-1.5 text-xs bg-primary/10 text-primary border border-primary/50 rounded cursor-pointer disabled:opacity-50">
              {alertLoading ? 'Saving...' : 'Save'}
            </button>
            <button onClick={async () => {
              try {
                await client.post('/alerts/test')
                addToast('Test alert sent!', 'success')
              } catch { addToast('Test alert failed', 'error') }
            }}
              className="px-3 py-1.5 text-xs bg-surface-elevated-dark text-muted border border-hairline-on-dark rounded cursor-pointer">
              Test Alert
            </button>
          </div>
        </div>
      </section>

      <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
        <h2 className="text-sm font-semibold text-body mb-1">About</h2>
        <div className="space-y-1 text-xs">
          <p className="text-muted">
            MT5 Paper Trading Receiver v2.1 — Multi-bot paper trading engine
          </p>
          <p className="text-muted">
            All trading is simulated in-memory and persisted to SQLite. No real orders are sent to MT5.
          </p>
          <p className="text-muted font-mono">
            Frontend: React + Vite + TS + Tailwind
          </p>
        </div>
      </section>
    </div>
  )
}
