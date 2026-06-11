import { useState, useEffect, useCallback } from 'react'
import client from '../api/client'
import type { MarketStructureState, OrderBlock, OrderBlockState, BosEvent } from '../types/api'

const log = (...args: unknown[]) => console.log('[MarketStructure]', ...args)

const TIMEFRAMES = ['M1', 'M5', 'M15', 'H1'] as const
type TF = (typeof TIMEFRAMES)[number]

export default function MarketStructure() {
  const [timeframe, setTimeframe] = useState<TF>('M15')
  const [structure, setStructure] = useState<MarketStructureState | null>(null)
  const [obState, setObState] = useState<OrderBlockState | null>(null)
  const [obActives, setObActives] = useState<OrderBlock[]>([])
  const [bosEvents, setBosEvents] = useState<BosEvent[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async (tf: TF) => {
    try {
      const [structRes, obRes, bosRes, obActiveRes] = await Promise.all([
        client.get<MarketStructureState>(`/market-structure/${tf}`),
        client.get<OrderBlockState>(`/order-blocks/state/${tf}`),
        client.get<BosEvent[]>(`/bos/${tf}`, { params: { limit: 20 } }),
        client.get<OrderBlock[]>(`/order-blocks/active/${tf}`, { params: { limit: 20 } }),
      ])
      setStructure(structRes.data)
      setObState(obRes.data)
      setBosEvents(bosRes.data)
      setObActives(obActiveRes.data)
    } catch (err) {
      log('fetch failed', err)
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number }; message?: string }
        log('status:', axiosErr.response?.status)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  const rebuild = useCallback(async () => {
    await client.post('/order-blocks/rebuild')
    fetchData(timeframe)
  }, [timeframe, fetchData])

  useEffect(() => {
    fetchData(timeframe)
  }, [timeframe, fetchData])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-text-muted text-sm font-mono">Loading...</div>
      </div>
    )
  }

  const highPrice = structure?.latest_swing_high?.price
  const lowPrice = structure?.latest_swing_low?.price
  const latestBos = structure?.latest_bos

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-text-primary">Market Structure</h1>
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`px-3 py-1.5 text-xs font-mono font-semibold rounded-md transition-colors cursor-pointer ${
                  timeframe === tf
                    ? 'bg-cyber-cyan/20 text-cyber-cyan border border-cyber-cyan/50'
                    : 'bg-surface-800 text-text-muted border border-surface-500 hover:border-surface-300'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
          <button
            onClick={rebuild}
            className="px-3 py-1.5 text-xs rounded-md bg-surface-700 text-text-secondary hover:text-text-primary border border-surface-500 transition-colors cursor-pointer"
          >
            Rebuild
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-surface-800 border border-surface-500 rounded-lg p-4">
          <p className="text-xs text-text-muted mb-3 uppercase tracking-wider font-semibold">Swings</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-text-muted">Latest High</p>
              <p className="font-mono text-lg font-semibold text-cyber-green">
                {highPrice != null ? highPrice.toFixed(2) : '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-text-muted">Latest Low</p>
              <p className="font-mono text-lg font-semibold text-cyber-red">
                {lowPrice != null ? lowPrice.toFixed(2) : '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-text-muted">Total Swings</p>
              <p className="font-mono text-lg font-semibold text-text-primary">
                {structure?.counts?.swings ?? 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-surface-800 border border-surface-500 rounded-lg p-4">
          <p className="text-xs text-text-muted mb-3 uppercase tracking-wider font-semibold">Break of Structure</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-text-muted">Total BOS</p>
              <p className="font-mono text-lg font-semibold text-text-primary">
                {structure?.counts?.bos ?? 0}
              </p>
            </div>
            <div>
              <p className="text-xs text-text-muted">Latest</p>
              <p className={`font-mono text-lg font-semibold ${latestBos?.side === 'bullish' ? 'text-cyber-green' : 'text-cyber-red'}`}>
                {latestBos?.side ? latestBos.side.toUpperCase() : '—'}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-surface-800 border border-surface-500 rounded-lg p-4">
          <p className="text-xs text-text-muted mb-3 uppercase tracking-wider font-semibold">Order Blocks</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-text-muted">Active Strong</p>
              <p className="font-mono text-lg font-semibold text-cyber-cyan">{obState?.strong_count ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-text-muted">Total Active</p>
              <p className="font-mono text-lg font-semibold text-text-primary">{obState?.active_total ?? 0}</p>
            </div>
          </div>
        </div>
      </div>

      {obActives.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Active Order Blocks</h2>
          <div className="bg-surface-800 border border-surface-500 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-500 text-text-muted text-xs">
                  <th className="text-left p-3 font-medium">Side</th>
                  <th className="text-right p-3 font-medium">Open</th>
                  <th className="text-right p-3 font-medium">Close</th>
                  <th className="text-right p-3 font-medium">High</th>
                  <th className="text-right p-3 font-medium">Low</th>
                  <th className="text-right p-3 font-medium">Score</th>
                  <th className="text-right p-3 font-medium">Retests</th>
                  <th className="text-left p-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {obActives.map((ob) => (
                  <tr key={ob.id} className="border-b border-surface-600">
                    <td className={`p-3 font-mono text-xs font-semibold ${ob.side === 'buy' ? 'text-cyber-green' : 'text-cyber-red'}`}>
                      {ob.side.toUpperCase()}
                    </td>
                    <td className="p-3 font-mono text-xs text-right">{ob.ob_open.toFixed(2)}</td>
                    <td className="p-3 font-mono text-xs text-right">{ob.ob_close.toFixed(2)}</td>
                    <td className="p-3 font-mono text-xs text-right">{ob.ob_high.toFixed(2)}</td>
                    <td className="p-3 font-mono text-xs text-right">{ob.ob_low.toFixed(2)}</td>
                    <td className="p-3 font-mono text-xs text-right">{ob.score}</td>
                    <td className="p-3 font-mono text-xs text-right">{ob.retest_count}</td>
                    <td className="p-3">
                      <span className={`text-xs font-mono ${ob.is_strong ? 'text-cyber-cyan' : 'text-text-muted'}`}>
                        {ob.status}{ob.is_strong ? ' ★' : ''}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {bosEvents.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Recent BOS Events</h2>
          <div className="bg-surface-800 border border-surface-500 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-500 text-text-muted text-xs">
                  <th className="text-left p-3 font-medium">Side</th>
                  <th className="text-right p-3 font-medium">Break Price</th>
                  <th className="text-right p-3 font-medium">Time</th>
                </tr>
              </thead>
              <tbody>
                {bosEvents.map((bos) => (
                  <tr key={bos.id} className="border-b border-surface-600">
                    <td className={`p-3 font-mono text-xs font-semibold ${bos.side === 'bullish' ? 'text-cyber-green' : 'text-cyber-red'}`}>
                      {bos.side.toUpperCase()}
                    </td>
                    <td className="p-3 font-mono text-xs text-right">{bos.break_close.toFixed(2)}</td>
                    <td className="p-3 text-xs text-text-muted font-mono">
                      {new Date(bos.created_at * 1000).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
