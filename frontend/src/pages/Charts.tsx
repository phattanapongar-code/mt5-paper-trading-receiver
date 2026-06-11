import { useEffect, useRef, useState, useCallback } from 'react'
import { createChart, ColorType, type IChartApi, type ISeriesApi, type CandlestickData, type LineData, type UTCTimestamp, CandlestickSeries, LineSeries } from 'lightweight-charts'
import client from '../api/client'
import type { Candle, Indicators } from '../types/api'

const TIMEFRAMES = ['M1', 'M5', 'M15', 'H1'] as const
type TF = (typeof TIMEFRAMES)[number]

export default function Charts() {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartApiRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const ma60SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma80SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma300SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)

  const [timeframe, setTimeframe] = useState<TF>('M15')
  const [candles, setCandles] = useState<Candle[]>([])
  const [indicators, setIndicators] = useState<Indicators | null>(null)

  const fetchCandles = useCallback(async (tf: TF) => {
    try {
      const [candleRes, indRes] = await Promise.all([
        client.get<Candle[]>(`/candles/${tf}`, { params: { limit: 200, closed_only: false } }),
        client.get<Indicators>(`/indicators/${tf}`),
      ])
      setCandles(candleRes.data)
      setIndicators(indRes.data)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    fetchCandles(timeframe)
    const interval = setInterval(() => fetchCandles(timeframe), 5000)
    return () => clearInterval(interval)
  }, [timeframe, fetchCandles])

  useEffect(() => {
    if (!chartRef.current) return

    const chart = createChart(chartRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#0a0a18' },
        textColor: '#64748b',
      },
      grid: {
        vertLines: { color: '#1a1a3e' },
        horzLines: { color: '#1a1a3e' },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: '#3a3a6a', width: 1, style: 2 },
        horzLine: { color: '#3a3a6a', width: 1, style: 2 },
      },
      timeScale: {
        borderColor: '#2a2a5a',
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: '#2a2a5a',
      },
      width: chartRef.current.clientWidth,
      height: 500,
    })

    const candlesSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#00ff88',
      downColor: '#ff3355',
      borderUpColor: '#00ff88',
      borderDownColor: '#ff3355',
      wickUpColor: '#00ff88',
      wickDownColor: '#ff3355',
    })

    const ma60 = chart.addSeries(LineSeries, {
      color: '#00f0ff',
      lineWidth: 1,
      lastValueVisible: false,
      priceFormat: { type: 'custom' as const, formatter: (p: number) => p.toFixed(2) },
    })
    const ma80 = chart.addSeries(LineSeries, {
      color: '#ffcc00',
      lineWidth: 1,
      lastValueVisible: false,
      priceFormat: { type: 'custom' as const, formatter: (p: number) => p.toFixed(2) },
    })
    const ma300 = chart.addSeries(LineSeries, {
      color: '#8833ff',
      lineWidth: 1,
      lastValueVisible: false,
      priceFormat: { type: 'custom' as const, formatter: (p: number) => p.toFixed(2) },
    })

    chartApiRef.current = chart
    candleSeriesRef.current = candlesSeries
    ma60SeriesRef.current = ma60
    ma80SeriesRef.current = ma80
    ma300SeriesRef.current = ma300

    const handleResize = () => {
      if (chartRef.current) {
        chart.applyOptions({ width: chartRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [])

  useEffect(() => {
    if (!candleSeriesRef.current) return

    const candleData: CandlestickData[] = candles
      .filter((c) => c.open_time && c.close)
      .map((c) => ({
        time: c.open_time as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
      .sort((a, b) => Number(a.time) - Number(b.time))

    candleSeriesRef.current.setData(candleData)

    if (ma60SeriesRef.current && indicators?.ma60 != null) {
      const lineData: LineData[] = candles
        .filter((c) => c.open_time)
        .map((c) => ({ time: c.open_time as UTCTimestamp, value: indicators.ma60! }))
        .sort((a, b) => Number(a.time) - Number(b.time))
      ma60SeriesRef.current.setData(lineData)
    }
    if (ma80SeriesRef.current && indicators?.ma80 != null) {
      const lineData: LineData[] = candles
        .filter((c) => c.open_time)
        .map((c) => ({ time: c.open_time as UTCTimestamp, value: indicators.ma80! }))
        .sort((a, b) => Number(a.time) - Number(b.time))
      ma80SeriesRef.current.setData(lineData)
    }
    if (ma300SeriesRef.current && indicators?.ma300 != null) {
      const lineData: LineData[] = candles
        .filter((c) => c.open_time)
        .map((c) => ({ time: c.open_time as UTCTimestamp, value: indicators.ma300! }))
        .sort((a, b) => Number(a.time) - Number(b.time))
      ma300SeriesRef.current.setData(lineData)
    }
  }, [candles, indicators])

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-text-primary">Charts</h1>
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
      </div>

      <div ref={chartRef} className="rounded-lg overflow-hidden border border-surface-500" />

      {indicators && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <IndiCard label="MA60" value={indicators.ma60?.toFixed(2) ?? '—'} color="#00f0ff" />
          <IndiCard label="MA80" value={indicators.ma80?.toFixed(2) ?? '—'} color="#ffcc00" />
          <IndiCard label="MA300" value={indicators.ma300?.toFixed(2) ?? '—'} color="#8833ff" />
          <IndiCard label="ATR14" value={indicators.atr14?.toFixed(2) ?? '—'} color="#ff33cc" />
          <IndiCard
            label="Trend"
            value={indicators.trend ?? '—'}
            color={indicators.trend === 'BULLISH' ? '#00ff88' : indicators.trend === 'BEARISH' ? '#ff3355' : '#64748b'}
          />
        </div>
      )}
    </div>
  )
}

function IndiCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-surface-800 border border-surface-500 rounded-lg p-3">
      <p className="text-xs text-text-muted mb-0.5">{label}</p>
      <p className="font-mono text-sm font-semibold" style={{ color }}>{value}</p>
    </div>
  )
}
