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

  const rebuildMarketStructure = useCallback(async () => {
    try {
      await client.post('/market-structure/rebuild')
      fetchData(timeframe)
    } catch (err) {
      log('rebuild market structure failed', err)
    }
  }, [timeframe, fetchData])

  useEffect(() => {
    fetchData(timeframe)
  }, [timeframe, fetchData])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-muted text-sm font-mono">Loading...</div>
      </div>
    )
  }

  const highPrice = structure?.latest_swing_high?.price
  const lowPrice = structure?.latest_swing_low?.price
  const latestBos = structure?.latest_bos

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-body">Market Structure</h1>
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              {TIMEFRAMES.map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={`px-3 py-1.5 text-xs font-mono font-semibold rounded-md transition-colors cursor-pointer ${
                    timeframe === tf
                      ? 'bg-primary/10 text-primary border border-primary/50'
                      : 'bg-surface-card-dark text-muted border border-hairline-on-dark hover:border-surface-elevated-dark'
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
            <div className="flex gap-1">
              <button
                onClick={rebuild}
                className="px-3 py-1.5 text-xs rounded-md bg-surface-elevated-dark text-text-secondary hover:text-body border border-hairline-on-dark transition-colors cursor-pointer"
              >
                Rebuild Order Blocks
              </button>
              <button
                onClick={rebuildMarketStructure}
                className="px-3 py-1.5 text-xs rounded-md bg-primary/10 text-primary border border-primary/50 hover:bg-primary/20 transition-colors cursor-pointer"
              >
                Rebuild Market Structure
              </button>
            </div>
          </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <p className="text-xs text-muted mb-3 uppercase tracking-wider font-semibold">Swings</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-muted">Latest High</p>
              <p className="font-mono text-lg font-semibold text-trading-up">
                {highPrice != null ? highPrice.toFixed(2) : '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted">Latest Low</p>
              <p className="font-mono text-lg font-semibold text-trading-down">
                {lowPrice != null ? lowPrice.toFixed(2) : '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted">Total Swings</p>
              <p className="font-mono text-lg font-semibold text-body">
                {structure?.counts?.swings ?? 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <p className="text-xs text-muted mb-3 uppercase tracking-wider font-semibold">Break of Structure</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-muted">Total BOS</p>
              <p className="font-mono text-lg font-semibold text-body">
                {structure?.counts?.bos ?? 0}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted">Latest</p>
              <p className={`font-mono text-lg font-semibold ${latestBos?.side === 'bullish' ? 'text-trading-up' : 'text-trading-down'}`}>
                {latestBos?.side ? latestBos.side.toUpperCase() : '—'}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <p className="text-xs text-muted mb-3 uppercase tracking-wider font-semibold">Order Blocks</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-muted">Active Strong</p>
              <p className="font-mono text-lg font-semibold text-primary">{obState?.strong_count ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-muted">Total Active</p>
              <p className="font-mono text-lg font-semibold text-body">{obState?.active_total ?? 0}</p>
            </div>
          </div>
        </div>
      </div>

      {obActives.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Active Order Blocks</h2>
          <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline-on-dark text-muted text-xs">
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
                  <tr key={ob.id} className="border-b border-surface-elevated-dark">
                    <td className={`p-3 font-mono text-xs font-semibold ${ob.side === 'buy' ? 'text-trading-up' : 'text-trading-down'}`}>
                      {ob.side.toUpperCase()}
                    </td>
                    <td className="p-3 font-mono text-xs text-right">{ob.ob_open.toFixed(2)}</td>
                    <td className="p-3 font-mono text-xs text-right">{ob.ob_close.toFixed(2)}</td>
                    <td className="p-3 font-mono text-xs text-right">{ob.ob_high.toFixed(2)}</td>
                    <td className="p-3 font-mono text-xs text-right">{ob.ob_low.toFixed(2)}</td>
                    <td className="p-3 font-mono text-xs text-right">{ob.score}</td>
                    <td className="p-3 font-mono text-xs text-right">{ob.retest_count}</td>
                    <td className="p-3">
                      <span className={`text-xs font-mono ${ob.is_strong ? 'text-primary' : 'text-muted'}`}>
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
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Recent BOS Events</h2>
          <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline-on-dark text-muted text-xs">
                  <th className="text-left p-3 font-medium">Side</th>
                  <th className="text-right p-3 font-medium">Break Price</th>
                  <th className="text-right p-3 font-medium">Time</th>
                </tr>
              </thead>
              <tbody>
                {bosEvents.map((bos) => (
                  <tr key={bos.id} className="border-b border-surface-elevated-dark">
                    <td className={`p-3 font-mono text-xs font-semibold ${bos.side === 'bullish' ? 'text-trading-up' : 'text-trading-down'}`}>
                      {bos.side.toUpperCase()}
                    </td>
                    <td className="p-3 font-mono text-xs text-right">{bos.break_close.toFixed(2)}</td>
                    <td className="p-3 text-xs text-muted font-mono">
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
