import { useState, useCallback } from 'react'
import client from '../api/client'
import type { ReplayRun } from '../types/api'

interface Props {
  onRun?: () => void
}

export default function ReplayViewer({ onRun }: Props) {
  const [latest, setLatest] = useState<ReplayRun | null>(null)
  const [running, setRunning] = useState(false)

  const run = useCallback(async () => {
    setRunning(true)
    try {
      const [runRes, latestRes] = await Promise.all([
        client.post('/replay/run'),
        client.get<ReplayRun>('/replay/latest'),
      ])
      setLatest(latestRes.data ?? runRes.data)
      onRun?.()
    } catch {
      alert('Replay failed')
    } finally {
      setRunning(false)
    }
  }, [onRun])

  const loadLatest = useCallback(async () => {
    try {
      const res = await client.get<ReplayRun>('/replay/latest')
      setLatest(res.data)
    } catch {
      // ignore
    }
  }, [])

  useState(() => { loadLatest() })

  return (
    <div className="bg-surface-800 border border-surface-500 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider">Replay Runner</h2>
        <button onClick={run} disabled={running}
          className="px-3 py-1.5 text-xs bg-cyber-cyan/20 text-cyber-cyan border border-cyber-cyan/50 rounded disabled:opacity-40 cursor-pointer">
          {running ? 'Running...' : 'Run Replay'}
        </button>
      </div>
      {latest && (
        <div className="text-xs font-mono text-text-muted bg-surface-900 rounded p-3 max-h-48 overflow-y-auto whitespace-pre-wrap">
          {latest.payload}
        </div>
      )}
      {!latest && (
        <p className="text-xs text-text-muted">No replay runs yet</p>
      )}
    </div>
  )
}
