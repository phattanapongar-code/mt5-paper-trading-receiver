import { useState, useEffect, useCallback, useRef } from 'react'
import client from '../api/client'
import type { ExecutionState, Health, HistoryStatus } from '../types/api'

const log = (...args: unknown[]) => console.log('[Settings]', ...args)

export default function Settings() {
  const [exec, setExec] = useState<ExecutionState | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [historyStatus, setHistoryStatus] = useState<HistoryStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const historyFileInputRef = useRef<HTMLInputElement>(null)

  const fetchData = useCallback(async () => {
    try {
      const [execRes, historyStatusRes] = await Promise.all([
        client.get<ExecutionState>('/strategy/status'),
        client.get<HistoryStatus>('/history/status'),
      ])
      setExec(execRes.data)
      setHistoryStatus(historyStatusRes.data)
      try {
        const healthRes = await fetch('/health')
        if (healthRes.ok) setHealth(await healthRes.json())
      } catch {
        log('health fetch failed')
      }
    } catch {
    } finally {
      setLoading(false)
    }
  }, [])

  const toggleExecution = useCallback(async (enable: boolean) => {
    const endpoint = enable ? 'enable' : 'disable'
    await client.post(`/strategy/${endpoint}`)
    fetchData()
  }, [fetchData])

  const resetPaper = useCallback(async () => {
    if (confirm('Reset paper account? This will delete all trades.')) {
      await client.post('/paper/reset')
      fetchData()
    }
  }, [fetchData])

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

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <h1 className="text-lg font-semibold text-body">Settings</h1>

      <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
        <h2 className="text-sm font-semibold text-body mb-1">Auto Paper Execution</h2>
        <p className="text-xs text-muted mb-3">Automatically fills staged pending orders into the paper account (paper-only, never sends to MT5)</p>
        <div className="flex items-center gap-3">
          <div className={`px-3 py-1.5 text-xs rounded-md font-semibold border ${exec?.enabled ? 'bg-trading-up/10 text-trading-up border border-trading-up/50' : 'bg-surface-elevated-dark text-muted border border-surface-400'}`}>
            {exec?.enabled ? 'ENABLED' : 'DISABLED'}
          </div>
          <button
            onClick={() => toggleExecution(!exec?.enabled)}
            className={`px-3 py-1.5 text-xs rounded-md font-semibold transition-colors cursor-pointer ${
              exec?.enabled
                ? 'bg-trading-down/10 text-trading-down border border-trading-down/50 hover:bg-trading-down/20'
                : 'bg-trading-up/10 text-trading-up border border-trading-up/50 hover:bg-trading-up/20'
            }`}
            title={exec?.enabled ? "Click to disable auto execution" : "Click to enable auto execution"}
          >
            {exec?.enabled ? 'DISABLE AUTO' : 'ENABLE AUTO'}
          </button>
        </div>
      </section>

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
        <div className="flex gap-2">
          <button
            onClick={resetPaper}
            className="px-3 py-1.5 text-xs rounded-md bg-trading-down/10 text-trading-down border border-trading-down/50 hover:bg-trading-down/20 transition-colors cursor-pointer"
          >
            Reset Paper Account
          </button>
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
        <h2 className="text-sm font-semibold text-body mb-1">About</h2>
        <div className="space-y-1 text-xs">
          <p className="text-muted">
            MT5 Paper Trading Receiver v1.2 — Multi-bot paper trading engine
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
