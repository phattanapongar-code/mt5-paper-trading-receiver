import { useState, useEffect, useCallback } from 'react'
import client from '../api/client'
import type { ExecutionState, Health } from '../types/api'

const log = (...args: unknown[]) => console.log('[Settings]', ...args)

export default function Settings() {
  const [exec, setExec] = useState<ExecutionState | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    try {
      const [execRes] = await Promise.all([
        client.get<ExecutionState>('/strategy/status'),
      ])
      setExec(execRes.data)
      try {
        const healthRes = await fetch('/health')
        if (healthRes.ok) setHealth(await healthRes.json())
      } catch {
        log('health fetch failed')
      }
    } catch {
      // ignore
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

  const rebuildAll = useCallback(async () => {
    await client.post('/order-blocks/rebuild')
    fetchData()
  }, [fetchData])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-text-muted text-sm font-mono">Loading...</div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <h1 className="text-lg font-semibold text-text-primary">Settings</h1>

      <section className="bg-surface-800 border border-surface-500 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-text-primary mb-1">Auto Paper Execution</h2>
        <p className="text-xs text-text-muted mb-3">Automatically fills staged pending orders into the paper account (paper-only, never sends to MT5)</p>
        <div className="flex items-center gap-3">
          <div className={`px-3 py-1.5 text-xs rounded-md font-semibold border ${exec?.enabled ? 'bg-cyber-green/20 text-cyber-green border-cyber-green/50' : 'bg-surface-600 text-text-muted border-surface-400'}`}>
            {exec?.enabled ? 'ENABLED' : 'DISABLED'}
          </div>
          <button
            onClick={() => toggleExecution(!exec?.enabled)}
            className={`px-3 py-1.5 text-xs rounded-md font-semibold transition-colors cursor-pointer ${
              exec?.enabled
                ? 'bg-cyber-red/20 text-cyber-red border border-cyber-red/50 hover:bg-cyber-red/30'
                : 'bg-cyber-green/20 text-cyber-green border border-cyber-green/50 hover:bg-cyber-green/30'
            }`}
          >
            {exec?.enabled ? 'Disable' : 'Enable'}
          </button>
        </div>
      </section>

      <section className="bg-surface-800 border border-surface-500 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-text-primary mb-1">System</h2>
        {health && (
          <div className="grid grid-cols-2 gap-3 text-xs mb-3">
            <div>
              <span className="text-text-muted">Sender Status: </span>
              <span className={`font-mono ${health.sender_online ? 'text-cyber-green' : 'text-cyber-red'}`}>
                {health.sender_online ? 'ONLINE' : 'OFFLINE'}
              </span>
            </div>
            <div>
              <span className="text-text-muted">WebSocket Clients: </span>
              <span className="font-mono text-text-primary">{health.websocket_clients}</span>
            </div>
            <div>
              <span className="text-text-muted">Last Seq: </span>
              <span className="font-mono text-text-primary">{health.last_seq ?? '—'}</span>
            </div>
            <div>
              <span className="text-text-muted">Last Tick: </span>
              <span className="font-mono text-text-primary">
                {health.seconds_since_last_message != null ? `${health.seconds_since_last_message}s ago` : '—'}
              </span>
            </div>
          </div>
        )}
        <div className="flex gap-2">
          <button
            onClick={rebuildAll}
            className="px-3 py-1.5 text-xs rounded-md bg-surface-700 text-text-secondary hover:text-text-primary border border-surface-500 transition-colors cursor-pointer"
          >
            Rebuild Order Blocks
          </button>
          <button
            onClick={resetPaper}
            className="px-3 py-1.5 text-xs rounded-md bg-cyber-red/20 text-cyber-red border border-cyber-red/50 hover:bg-cyber-red/30 transition-colors cursor-pointer"
          >
            Reset Paper Account
          </button>
        </div>
      </section>

      <section className="bg-surface-800 border border-surface-500 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-text-primary mb-1">About</h2>
        <div className="space-y-1 text-xs">
          <p className="text-text-muted">
            MT5 Paper Trading Receiver v1.2 — Multi-bot paper trading engine
          </p>
          <p className="text-text-muted">
            All trading is simulated in-memory and persisted to SQLite. No real orders are sent to MT5.
          </p>
          <p className="text-text-muted font-mono">
            Frontend: React + Vite + TS + Tailwind
          </p>
        </div>
      </section>
    </div>
  )
}
