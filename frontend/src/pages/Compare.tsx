import { useEffect, useRef, useState } from 'react'
import { createChart, HistogramSeries, type IChartApi, type ISeriesApi, type HistogramData } from 'lightweight-charts'
import client from '../api/client'
import type { CompareBot } from '../types/api'

export default function Compare() {
  const pnlChartRef = useRef<HTMLDivElement>(null)
  const wrChartRef = useRef<HTMLDivElement>(null)
  const pnlChartApi = useRef<IChartApi | null>(null)
  const wrChartApi = useRef<IChartApi | null>(null)
  const pnlSeries = useRef<ISeriesApi<'Histogram'> | null>(null)
  const wrSeries = useRef<ISeriesApi<'Histogram'> | null>(null)

  const [data, setData] = useState<CompareBot[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    client.get<CompareBot[]>('/compare').then((r) => setData(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!data.length || !pnlChartRef.current || !wrChartRef.current) return

    // PnL chart
    if (!pnlChartApi.current) {
      pnlChartApi.current = createChart(pnlChartRef.current, {
        width: pnlChartRef.current.clientWidth,
        height: 200,
        layout: { background: { color: '#1e2329' }, textColor: '#eaecef' },
        grid: { vertLines: { color: '#2b3139' }, horzLines: { color: '#2b3139' } },
        rightPriceScale: { borderColor: '#2b3139' },
        timeScale: { visible: false, borderColor: '#2b3139' },
        crosshair: { vertLine: { visible: false }, horzLine: { visible: false } },
      })
      pnlSeries.current = pnlChartApi.current.addSeries(HistogramSeries, {
        color: '#0ecb81',
        priceFormat: { type: 'volume' },
      })
    }

    if (pnlSeries.current) {
      const pnlData: HistogramData[] = data.map((b, i) => ({
        time: (i + 1) as any,
        value: Math.abs(b.net_pnl ?? 0),
        color: (b.net_pnl ?? 0) >= 0 ? '#0ecb81' : '#f6465d',
      }))
      pnlSeries.current.setData(pnlData)
    }

    // Win rate chart
    if (!wrChartApi.current) {
      wrChartApi.current = createChart(wrChartRef.current, {
        width: wrChartRef.current.clientWidth,
        height: 200,
        layout: { background: { color: '#1e2329' }, textColor: '#eaecef' },
        grid: { vertLines: { color: '#2b3139' }, horzLines: { color: '#2b3139' } },
        rightPriceScale: { borderColor: '#2b3139' },
        timeScale: { visible: false, borderColor: '#2b3139' },
        crosshair: { vertLine: { visible: false }, horzLine: { visible: false } },
      })
      wrSeries.current = wrChartApi.current.addSeries(HistogramSeries, {
        color: '#FCD535',
        priceFormat: { type: 'volume' },
      })
    }

    if (wrSeries.current) {
      const wrData: HistogramData[] = data.map((b, i) => ({
        time: (i + 1) as any,
        value: b.closed_trades > 0 ? (b.win_rate ?? 0) * 100 : 0,
        color: (b.win_rate ?? 0) >= 0.5 ? '#0ecb81' : '#f6465d',
      }))
      wrSeries.current.setData(wrData)
    }

    const handleResize = () => {
      if (pnlChartRef.current && pnlChartApi.current) {
        pnlChartApi.current.resize(pnlChartRef.current.clientWidth, 200)
      }
      if (wrChartRef.current && wrChartApi.current) {
        wrChartApi.current.resize(wrChartRef.current.clientWidth, 200)
      }
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [data])

  useEffect(() => {
    return () => {
      pnlChartApi.current?.remove()
      wrChartApi.current?.remove()
    }
  }, [])

  if (loading) return <div className="text-muted text-xs p-6">Loading...</div>
  if (!data.length) return <div className="text-muted text-xs p-6">No bots to compare.</div>

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-semibold text-body">Compare Bots</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <p className="text-xs text-muted mb-2 uppercase tracking-wider font-semibold">PnL by Bot</p>
          <div ref={pnlChartRef} className="w-full" />
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
            {data.map((b, i) => (
              <span key={b.bot_id} className="text-xs text-muted font-mono">#{i + 1} {b.name}</span>
            ))}
          </div>
        </div>
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <p className="text-xs text-muted mb-2 uppercase tracking-wider font-semibold">Win Rate by Bot</p>
          <div ref={wrChartRef} className="w-full" />
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
            {data.map((b, i) => (
              <span key={b.bot_id} className="text-xs text-muted font-mono">#{i + 1} {b.name}</span>
            ))}
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted uppercase tracking-wider border-b border-hairline-on-dark">
              <th className="text-left py-2 pr-3">Bot</th>
              <th className="text-left py-2 pr-3">Strategy</th>
              <th className="text-right py-2 pr-3">Balance</th>
              <th className="text-right py-2 pr-3">PnL</th>
              <th className="text-right py-2 pr-3">Win Rate</th>
              <th className="text-right py-2 pr-3">Trades</th>
              <th className="text-right py-2 pr-3">Max DD</th>
            </tr>
          </thead>
          <tbody>
            {data.map((b) => (
              <tr key={b.bot_id} className="border-b border-surface-elevated-dark text-body">
                <td className="py-2 pr-3">{b.name}
                  <span className="ml-2 text-muted">{b.profile_name}</span>
                </td>
                <td className="py-2 pr-3 font-mono text-xs">Visual</td>
                <td className="text-right py-2 pr-3 font-mono">${b.balance?.toFixed(2) ?? '0.00'}</td>
                <td className={`text-right py-2 pr-3 font-mono ${(b.net_pnl ?? 0) >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>
                  {(b.net_pnl ?? 0) >= 0 ? '+' : ''}{(b.net_pnl ?? 0).toFixed(2)}
                </td>
                <td className="text-right py-2 pr-3 font-mono">{b.closed_trades > 0 ? `${((b.win_rate ?? 0) * 100).toFixed(1)}%` : '-'}</td>
                <td className="text-right py-2 pr-3 font-mono">{b.closed_trades}</td>
                <td className="text-right py-2 pr-3 font-mono text-trading-down">{b.max_drawdown != null ? b.max_drawdown.toFixed(2) : '0.00'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}