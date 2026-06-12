import { useEffect, useRef, useState, useCallback } from 'react'
import { createChart, ColorType, createSeriesMarkers, type IChartApi, type ISeriesApi, type ISeriesMarkersPluginApi, type CandlestickData, type LineData, type UTCTimestamp, type Time, CandlestickSeries, LineSeries } from 'lightweight-charts'
import client from '../api/client'
import { useBotContext } from '../context/BotContext'
import type { Candle, Indicators, OrderBlock, MarketStructureState } from '../types/api'

interface CandlePendingOrder {
  id: number; bot_id?: number; side: string; entry: number; stop_loss: number; take_profit: number
}

const TIMEFRAMES = ['M1', 'M5', 'M15', 'H1'] as const
type TF = (typeof TIMEFRAMES)[number]

export default function Charts() {
  const { allBots } = useBotContext()
  const chartRef = useRef<HTMLDivElement>(null)
  const chartApiRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const ma60SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma80SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma300SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)

  const [timeframe, setTimeframe] = useState<TF>('M15')
  const [pendingBotId, setPendingBotId] = useState<number | null>(null)
  const [candles, setCandles] = useState<Candle[]>([])
  const [indicators, setIndicators] = useState<Indicators | null>(null)
  const [obs, setObs] = useState<OrderBlock[]>([])
  const [structure, setStructure] = useState<MarketStructureState | null>(null)
  const [pending, setPending] = useState<CandlePendingOrder | null>(null)

  const fetchData = useCallback(async (tf: TF) => {
    try {
      const pendingParams: Record<string, unknown> = { limit: 1 }
      if (pendingBotId) pendingParams.bot_id = pendingBotId
      const [candleRes, indRes, obRes, structRes, pendingRes] = await Promise.all([
        client.get<Candle[]>(`/candles/${tf}`, { params: { limit: 200, closed_only: false } }),
        client.get<Indicators>(`/indicators/${tf}`),
        client.get<OrderBlock[]>(`/order-blocks/active/${tf}`, { params: { limit: 10 } }),
        client.get<MarketStructureState>(`/market-structure/${tf}`),
        client.get<CandlePendingOrder[]>('/pending-orders', { params: pendingParams }),
      ])
      setCandles(candleRes.data)
      setIndicators(indRes.data)
      setObs(obRes.data)
      setStructure(structRes.data)
      setPending(pendingRes.data[0] ?? null)
    } catch {
      // ignore
    }
  }, [pendingBotId])

  useEffect(() => {
    fetchData(timeframe)
    const interval = setInterval(() => fetchData(timeframe), 5000)
    return () => clearInterval(interval)
  }, [timeframe, fetchData])

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

    markersPluginRef.current = createSeriesMarkers(candlesSeries)

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
      markersPluginRef.current = null
      chart.remove()
    }
  }, [])

  useEffect(() => {
    const series = candleSeriesRef.current
    if (!series) return

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

    series.setData(candleData)

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

    // clear old price lines
    const chart = chartApiRef.current
    if (chart) {
      const existing = (series as any).priceLines?.() ?? []
      for (const pl of existing) {
        try { (series as any).removePriceLine(pl) } catch {}
      }
    }

    // OB zones: horizontal lines at ob_high and ob_low
    for (const ob of obs) {
      const obColor = ob.side === 'buy' ? '#0ecb81' : '#f6465d'
      series.createPriceLine({ price: ob.ob_high, color: obColor, lineStyle: 2, lineWidth: 1, axisLabelVisible: true, title: `${ob.side.toUpperCase()} OB` })
      series.createPriceLine({ price: ob.ob_low, color: obColor, lineStyle: 2, lineWidth: 1, axisLabelVisible: false })
    }

    // Swing high/low lines
    if (structure?.latest_swing_high?.price) {
      series.createPriceLine({ price: structure.latest_swing_high.price, color: '#FCD535', lineStyle: 3, lineWidth: 1, axisLabelVisible: true, title: 'SW H' })
    }
    if (structure?.latest_swing_low?.price) {
      series.createPriceLine({ price: structure.latest_swing_low.price, color: '#FCD535', lineStyle: 3, lineWidth: 1, axisLabelVisible: true, title: 'SW L' })
    }

    // Pending order lines
    if (pending) {
      const pendColor = pending.side === 'buy' ? '#0ecb81' : '#f6465d'
      series.createPriceLine({ price: pending.entry, color: pendColor, lineStyle: 0, lineWidth: 2, axisLabelVisible: true, title: `PEND ${pending.side.toUpperCase()}` })
      series.createPriceLine({ price: pending.stop_loss, color: '#f6465d', lineStyle: 1, lineWidth: 1, axisLabelVisible: true, title: 'PEND SL' })
      series.createPriceLine({ price: pending.take_profit, color: '#0ecb81', lineStyle: 1, lineWidth: 1, axisLabelVisible: true, title: 'PEND TP' })
    }

    // Swing point markers
    const markers: { time: UTCTimestamp; position: 'aboveBar' | 'belowBar'; color: string; shape: 'arrowUp' | 'arrowDown'; text: string }[] = []
    if (structure?.latest_swing_high?.pivot_open_time) {
      markers.push({ time: structure.latest_swing_high.pivot_open_time as UTCTimestamp, position: 'belowBar', color: '#FCD535', shape: 'arrowDown', text: 'H' })
    }
    if (structure?.latest_swing_low?.pivot_open_time) {
      markers.push({ time: structure.latest_swing_low.pivot_open_time as UTCTimestamp, position: 'aboveBar', color: '#FCD535', shape: 'arrowUp', text: 'L' })
    }
    if (markers.length) {
      markersPluginRef.current?.setMarkers(markers)
    }
  }, [candles, indicators, obs, structure, pending])

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-lg font-semibold text-body">Charts</h1>
        <div className="flex gap-1 items-center">
          <select
            value={pendingBotId ?? ''}
            onChange={(e) => setPendingBotId(e.target.value ? Number(e.target.value) : null)}
            className="px-2 py-1.5 text-xs bg-surface-card-dark text-muted border border-hairline-on-dark rounded-md focus:outline-none focus:border-primary cursor-pointer"
          >
            <option value="">All Bots</option>
            {allBots.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
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

      {obs.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {obs.map((ob) => (
            <span key={ob.id} className={`text-xs px-2 py-1 rounded ${ob.side === 'buy' ? 'bg-trading-up/10 text-trading-up' : 'bg-trading-down/10 text-trading-down'} border ${ob.side === 'buy' ? 'border-trading-up/30' : 'border-trading-down/30'}`}>
              {ob.side.toUpperCase()} OB {ob.score}pts {ob.is_strong ? '★' : ''}
            </span>
          ))}
          <span className="text-xs text-muted self-center">{obs.length} active OBs</span>
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