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
        background: { type: ColorType.Solid, color: '#1e2329' },
        textColor: '#eaecef',
      },
      grid: {
        vertLines: { color: '#2b3139' },
        horzLines: { color: '#2b3139' },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: '#2b3139', width: 1, style: 2 },
        horzLine: { color: '#2b3139', width: 1, style: 2 },
      },
      timeScale: {
        borderColor: '#2b3139',
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: '#2b3139',
      },
      width: chartRef.current.clientWidth,
      height: 500,
    })

    const candlesSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#0ecb81',
      downColor: '#f6465d',
      borderUpColor: '#0ecb81',
      borderDownColor: '#f6465d',
      wickUpColor: '#0ecb81',
      wickDownColor: '#f6465d',
    })

    const ma60 = chart.addSeries(LineSeries, {
      color: '#FCD535',
      lineWidth: 1,
      lastValueVisible: false,
      priceFormat: { type: 'custom' as const, formatter: (p: number) => p.toFixed(2) },
    })
    const ma80 = chart.addSeries(LineSeries, {
      color: '#FCD535',
      lineWidth: 1,
      lastValueVisible: false,
      priceFormat: { type: 'custom' as const, formatter: (p: number) => p.toFixed(2) },
    })
    const ma300 = chart.addSeries(LineSeries, {
      color: '#FCD535',
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
        <h1 className="text-lg font-semibold text-body">Charts</h1>
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
      </div>

      <div ref={chartRef} className="rounded-lg overflow-hidden border border-hairline-on-dark" />

      {indicators && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <IndiCard label="MA60" value={indicators.ma60?.toFixed(2) ?? '—'} color="#FCD535" />
          <IndiCard label="MA80" value={indicators.ma80?.toFixed(2) ?? '—'} color="#FCD535" />
          <IndiCard label="MA300" value={indicators.ma300?.toFixed(2) ?? '—'} color="#FCD535" />
          <IndiCard label="ATR14" value={indicators.atr14?.toFixed(2) ?? '—'} color="#FCD535" />
          <IndiCard
            label="Trend"
            value={indicators.trend ?? '—'}
            color={indicators.trend === 'BULLISH' ? '#0ecb81' : indicators.trend === 'BEARISH' ? '#f6465d' : '#eaecef'}
          />
        </div>
      )}
    </div>
  )
}

function IndiCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-3">
      <p className="text-xs text-muted mb-0.5">{label}</p>
      <p className="font-mono text-sm font-semibold" style={{ color }}>{value}</p>
    </div>
  )
}
