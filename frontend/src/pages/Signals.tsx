import { useEffect, useState, useMemo } from 'react'
import client from '../api/client'
import type { BotSignalLog, Bot } from '../types/api'

export default function Signals() {
  const [logs, setLogs] = useState<BotSignalLog[]>([])
  const [bots, setBots] = useState<Bot[]>([])
  const [loading, setLoading] = useState(true)
  const [eventFilter, setEventFilter] = useState('all')
  const [botFilter, setBotFilter] = useState('all')

  useEffect(() => {
    Promise.all([
      client.get<BotSignalLog[]>('/signal-logs?limit=500'),
      client.get<Bot[]>('/bots'),
    ]).then(([logsRes, botsRes]) => {
      setLogs(logsRes.data)
      setBots(botsRes.data)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const eventTypes = useMemo(() => {
    const types = new Set(logs.map((l) => l.event_type))
    return ['all', ...Array.from(types).sort()]
  }, [logs])

  const filteredLogs = useMemo(() => {
    return logs.filter((l) => {
      if (eventFilter !== 'all' && l.event_type !== eventFilter) return false
      if (botFilter !== 'all' && String(l.bot_id) !== botFilter) return false
      return true
    })
  }, [logs, eventFilter, botFilter])

  const botName = (id?: number) => bots.find((b) => b.id === id)?.name ?? `#${id}`

  if (loading) return <div className="text-muted text-xs p-6">Loading...</div>

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-lg font-semibold text-body">Signal Logs</h1>
        <div className="flex gap-2">
          <select value={eventFilter} onChange={(e) => setEventFilter(e.target.value)}
            className="px-2 py-1.5 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded text-body focus:outline-none focus:border-primary">
            {eventTypes.map((et) => (
              <option key={et} value={et}>{et === 'all' ? 'All Events' : et}</option>
            ))}
          </select>
          <select value={botFilter} onChange={(e) => setBotFilter(e.target.value)}
            className="px-2 py-1.5 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded text-body focus:outline-none focus:border-primary">
            <option value="all">All Bots</option>
            {bots.map((b) => (
              <option key={b.id} value={String(b.id)}>{b.name} (#{b.id})</option>
            ))}
          </select>
          <span className="text-xs text-muted font-mono self-center">{filteredLogs.length} logs</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted uppercase tracking-wider border-b border-hairline-on-dark">
              <th className="text-left py-2 pr-3">Time</th>
              <th className="text-left py-2 pr-3">Bot</th>
              <th className="text-left py-2 pr-3">Event</th>
              <th className="text-left py-2 pr-3">Message</th>
            </tr>
          </thead>
          <tbody>
            {filteredLogs.map((log) => (
              <tr key={log.id} className="border-b border-surface-elevated-dark text-text-secondary">
                <td className="py-2 pr-3 whitespace-nowrap font-mono">{new Date(log.created_at * 1000).toLocaleString()}</td>
                <td className="py-2 pr-3">
                  <span className="font-mono text-primary">{botName(log.bot_id)}</span>
                </td>
                <td className="py-2 pr-3">
                  <span className="px-2 py-0.5 rounded bg-surface-elevated-dark text-muted">{log.event_type}</span>
                </td>
                <td className="py-2 pr-3 max-w-md truncate">{log.message}</td>
              </tr>
            ))}
            {filteredLogs.length === 0 && (
              <tr><td colSpan={4} className="py-4 text-center text-muted">No signal logs match the filters</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}