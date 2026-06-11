import { useEffect, useState } from 'react'
import client from '../api/client'
import type { BotSignalLog } from '../types/api'

export default function Signals() {
  const [logs, setLogs] = useState<BotSignalLog[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    client.get<BotSignalLog[]>('/signal-logs?limit=200').then((r) => setLogs(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-text-muted text-xs p-6">Loading...</div>

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-sm font-semibold text-text-primary">Signal Logs</h1>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-text-muted uppercase tracking-wider border-b border-surface-500">
              <th className="text-left py-2 pr-3">Time</th>
              <th className="text-left py-2 pr-3">Bot</th>
              <th className="text-left py-2 pr-3">Event</th>
              <th className="text-left py-2 pr-3">Message</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id} className="border-b border-surface-600 text-text-secondary">
                <td className="py-2 pr-3 whitespace-nowrap font-mono">{new Date(log.created_at * 1000).toLocaleString()}</td>
                <td className="py-2 pr-3 font-mono text-cyber-cyan">#{log.bot_id}</td>
                <td className="py-2 pr-3">
                  <span className="px-2 py-0.5 rounded bg-surface-700 text-text-muted">{log.event_type}</span>
                </td>
                <td className="py-2 pr-3 max-w-md truncate">{log.message}</td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr><td colSpan={4} className="py-4 text-center text-text-muted">No signal logs</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
