import { useState, useEffect, useCallback } from 'react'
import client from '../api/client'
import { FiPlay, FiCheck, FiX, FiAlertTriangle } from 'react-icons/fi'
import type { ReplayRun } from '../types/api'

interface Props {
  onRun?: () => void
}

interface ReplayPayload {
  symbol: string
  created_at: number
  strong_ob_candidates: number
  simulated: number
  wins: number
  losses: number
  unresolved: number
  win_rate_resolved: number
  net_r: number
  results: {
    ob_id: number
    side: string
    break_open_time: number
    entry: number
    stop_loss: number
    take_profit: number
    fill_time: number | null
    exit_time: number
    result: string
    r_multiple: number
  }[]
}

export default function ReplayViewer({ onRun }: Props) {
  const [latest, setLatest] = useState<ReplayRun | null>(null)
  const [running, setRunning] = useState(false)

  const loadLatest = useCallback(async () => {
    try {
      const res = await client.get<ReplayRun>('/replay/latest')
      setLatest(res.data)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => { loadLatest() }, [loadLatest])

  const run = useCallback(async () => {
    setRunning(true)
    try {
      await client.post('/replay/run')
      const latestRes = await client.get<ReplayRun>('/replay/latest')
      setLatest(latestRes.data)
      onRun?.()
    } catch {
      alert('Replay failed')
    } finally {
      setRunning(false)
    }
  }, [onRun])

  let payload: ReplayPayload | null = null
  if (latest?.payload) {
    try { payload = JSON.parse(typeof latest.payload === 'string' ? latest.payload : JSON.stringify(latest.payload)) } catch {}
  }

  return (
    <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">Replay Runner</h2>
          <p className="text-[10px] text-muted mt-0.5">Simulates existing strong M15 Order Blocks against historical M1 bars</p>
        </div>
        <button onClick={run} disabled={running}
          className="px-3 py-1.5 text-xs bg-primary/10 text-primary border border-primary/50 rounded disabled:opacity-40 cursor-pointer">
          <span className="inline-flex items-center gap-1.5">{running ? 'Running...' : <><FiPlay size={14} /> Run Replay</>}</span>
        </button>
      </div>

      {!latest && !payload && (
        <p className="text-xs text-muted">No replay runs yet. Click "Run Replay" to start.</p>
      )}

      {payload && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <StatBox label="OB Candidates" value={String(payload.strong_ob_candidates)} color="#eaecef" />
            <StatBox label="Simulated" value={String(payload.simulated)} color="#eaecef" />
            <StatBox label="Wins (TP)" value={String(payload.wins)} color="#0ecb81" />
            <StatBox label="Losses (SL)" value={String(payload.losses)} color="#f6465d" />
            <StatBox label="Unresolved" value={String(payload.unresolved)} color="#8c6cd8" />
            <StatBox label="Win Rate" value={payload.wins + payload.losses > 0 ? `${(payload.win_rate_resolved * 100).toFixed(0)}%` : '—'} color={payload.win_rate_resolved >= 0.5 ? '#0ecb81' : '#f6465d'} />
            <StatBox label="Net R" value={payload.net_r.toFixed(2)} color={payload.net_r >= 0 ? '#0ecb81' : '#f6465d'} />
            <StatBox label="Avg R/Trade" value={payload.simulated > 0 ? (payload.net_r / payload.simulated).toFixed(2) : '—'} color="#eaecef" />
          </div>

          {payload.results.length > 0 && (
            <div className="overflow-x-auto max-h-72 overflow-y-auto">
              <table className="w-full text-xs">
                <thead><tr className="border-b border-hairline-on-dark text-muted">
                  <th className="text-left p-2">#</th>
                  <th className="text-left p-2">Side</th>
                  <th className="text-right p-2">Entry</th>
                  <th className="text-right p-2">SL</th>
                  <th className="text-right p-2">TP</th>
                  <th className="text-right p-2">R</th>
                  <th className="text-left p-2">Result</th>
                </tr></thead>
                <tbody>
                  {payload.results.map((r, i) => (
                    <tr key={r.ob_id} className="border-b border-surface-elevated-dark">
                      <td className="p-2 font-mono text-muted">{i + 1}</td>
                      <td className={`p-2 font-mono ${r.side === 'buy' ? 'text-trading-up' : 'text-trading-down'}`}>{r.side.toUpperCase()}</td>
                      <td className="p-2 font-mono text-right">{r.entry.toFixed(2)}</td>
                      <td className="p-2 font-mono text-right">{r.stop_loss.toFixed(2)}</td>
                      <td className="p-2 font-mono text-right">{r.take_profit.toFixed(2)}</td>
                      <td className={`p-2 font-mono text-right ${r.r_multiple >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>{r.r_multiple.toFixed(2)}</td>
                      <td className="p-2">
                        <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                          r.result === 'tp' ? 'bg-trading-up/10 text-trading-up' :
                          r.result === 'sl' ? 'bg-trading-down/10 text-trading-down' :
                          'bg-surface-elevated-dark text-muted'
                        }`}>
                          <span className="inline-flex items-center gap-1">{r.result === 'tp' ? <><FiCheck size={12} /> TP</> : r.result === 'sl' ? <><FiX size={12} /> SL</> : r.result === 'open' ? 'Open' : 'Expired'}</span>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p className="text-[10px] text-muted italic border-t border-hairline-on-dark pt-2">
            <FiAlertTriangle size={12} className="inline-block mr-0.5" /> Research preview — uses M1 OHLC ranges, not real ticks. Results are directional only.
          </p>
        </>
      )}
    </div>
  )
}

function StatBox({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-surface-elevated-dark/50 border border-hairline-on-dark rounded p-2">
      <p className="text-[10px] text-muted">{label}</p>
      <p className="font-mono text-xs font-semibold" style={{ color }}>{value}</p>
    </div>
  )
}
