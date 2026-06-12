import { useEffect, useRef, useState, useCallback } from 'react'
import { createChart, ColorType, createSeriesMarkers, type IChartApi, type ISeriesApi, type ISeriesMarkersPluginApi, type CandlestickData, type LineData, type UTCTimestamp, type Time, CandlestickSeries, LineSeries } from 'lightweight-charts'
import client from '../api/client'
import { useBotContext } from '../context/BotContext'
import { useDrawingTools } from '../components/DrawingTools'
import LoadingSpinner from '../components/LoadingSpinner'
import type { Candle, Indicators, OrderBlock, MarketStructureState } from '../types/api'

interface CandlePendingOrder {
  id: number; bot_id?: number; side: string; entry: number; stop_loss: number; take_profit: number
}

const TIMEFRAMES = ['M1', 'M5', 'M15', 'H1'] as const
type TF = (typeof TIMEFRAMES)[number]

export default function Charts() {
  const { allBots } = useBotContext()
  const chartRef = useRef<HTMLDivElement>(null)
  const [chartApi, setChartApi] = useState<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const ma60SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma80SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma300SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)
  const priceLinesRef = useRef<ReturnType<ISeriesApi<'Candlestick'>['createPriceLine']>[]>([])

  const [timeframe, setTimeframe] = useState<TF>('M15')
  const [pendingBotId, setPendingBotId] = useState<number | null>(null)
  const [candles, setCandles] = useState<Candle[]>([])
  const [indicators, setIndicators] = useState<Indicators | null>(null)
  const [obs, setObs] = useState<OrderBlock[]>([])
  const [structure, setStructure] = useState<MarketStructureState | null>(null)
  const [pending, setPending] = useState<CandlePendingOrder | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [visibleIndicators, setVisibleIndicators] = useState<Record<string, boolean>>({ rsi: false, macd: false, bb: false })
  const rsiSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const rsiOverboughtRef = useRef<ISeriesApi<'Line'> | null>(null)
  const rsiOversoldRef = useRef<ISeriesApi<'Line'> | null>(null)
  const macdLineRef = useRef<ISeriesApi<'Line'> | null>(null)
  const macdSignalRef = useRef<ISeriesApi<'Line'> | null>(null)
  const bbUpperRef = useRef<ISeriesApi<'Line'> | null>(null)
  const bbLowerRef = useRef<ISeriesApi<'Line'> | null>(null)
  const bbMiddleRef = useRef<ISeriesApi<'Line'> | null>(null)

  const toggleIndicator = useCallback((key: string) => {
    setVisibleIndicators(prev => {
      const next = { ...prev, [key]: !prev[key] }
      return next
    })
  }, [])

  const {
    activeTool, setActiveTool, color, setColor, selectedId, drawingCount,
    overlayRef, handlers, clearAll,
    renderDrawings, liveSvg,
  } = useDrawingTools(chartApi, chartRef as React.RefObject<HTMLDivElement | null>)

  const fetchData = useCallback(async (tf: TF) => {
    setRefreshing(true)
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
    } finally {
      setRefreshing(false)
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
      title: 'MA60',
    })
    const ma80 = chart.addSeries(LineSeries, {
      color: '#5e7cc4',
      lineWidth: 1,
      lastValueVisible: false,
      priceFormat: { type: 'custom' as const, formatter: (p: number) => p.toFixed(2) },
      title: 'MA80',
    })
    const ma300 = chart.addSeries(LineSeries, {
      color: '#8c6cd8',
      lineWidth: 1,
      lastValueVisible: false,
      priceFormat: { type: 'custom' as const, formatter: (p: number) => p.toFixed(2) },
      title: 'MA300',
    })

    markersPluginRef.current = createSeriesMarkers(candlesSeries)

    setChartApi(chart)
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

  function computeSma(data: CandlestickData[], period: number): LineData[] {
    return data.map((c, i) => {
      if (i < period - 1) return { time: c.time, value: NaN }
      let sum = 0
      for (let j = 0; j < period; j++) sum += data[i - j].close
      return { time: c.time, value: sum / period }
    }).filter(d => !isNaN(d.value))
  }

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

    if (ma60SeriesRef.current) {
      ma60SeriesRef.current.setData(computeSma(candleData, 60))
    }
    if (ma80SeriesRef.current) {
      ma80SeriesRef.current.setData(computeSma(candleData, 80))
    }
    if (ma300SeriesRef.current) {
      ma300SeriesRef.current.setData(computeSma(candleData, 300))
    }

    // Remove old price lines
    for (const pl of priceLinesRef.current) {
      try { series.removePriceLine(pl) } catch { /* already removed */ }
    }
    priceLinesRef.current = []

    const addPriceLine = (opts: Parameters<ISeriesApi<'Candlestick'>['createPriceLine']>[0]) => {
      priceLinesRef.current.push(series.createPriceLine(opts))
    }

    // OB zones: horizontal lines at ob_high and ob_low
    for (const ob of obs) {
      const obColor = ob.side === 'buy' ? '#0ecb81' : '#f6465d'
      addPriceLine({ price: ob.ob_high, color: obColor, lineStyle: 2, lineWidth: 1, axisLabelVisible: true, title: `${ob.side.toUpperCase()} OB` })
      addPriceLine({ price: ob.ob_low, color: obColor, lineStyle: 2, lineWidth: 1, axisLabelVisible: false })
    }

    // Swing high/low lines
    if (structure?.latest_swing_high?.price) {
      addPriceLine({ price: structure.latest_swing_high.price, color: '#FCD535', lineStyle: 3, lineWidth: 1, axisLabelVisible: true, title: 'SW H' })
    }
    if (structure?.latest_swing_low?.price) {
      addPriceLine({ price: structure.latest_swing_low.price, color: '#FCD535', lineStyle: 3, lineWidth: 1, axisLabelVisible: true, title: 'SW L' })
    }

    // Pending order lines
    if (pending) {
      const pendColor = pending.side === 'buy' ? '#0ecb81' : '#f6465d'
      addPriceLine({ price: pending.entry, color: pendColor, lineStyle: 0, lineWidth: 2, axisLabelVisible: true, title: `PEND ${pending.side.toUpperCase()}` })
      addPriceLine({ price: pending.stop_loss, color: '#f6465d', lineStyle: 1, lineWidth: 1, axisLabelVisible: true, title: 'PEND SL' })
      addPriceLine({ price: pending.take_profit, color: '#0ecb81', lineStyle: 1, lineWidth: 1, axisLabelVisible: true, title: 'PEND TP' })
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

    // Indicator overlays on main chart
    const chart = chartApi
    if (!chart) return

    // RSI overlay
    if (visibleIndicators.rsi) {
      if (!rsiSeriesRef.current) {
        rsiSeriesRef.current = chart.addSeries(LineSeries, {
          color: '#8c6cd8', lineWidth: 1, title: 'RSI(14)',
          priceFormat: { type: 'custom' as const, formatter: (p: number) => p.toFixed(2) },
        })
        rsiOverboughtRef.current = chart.addSeries(LineSeries, {
          color: '#f6465d', lineWidth: 1, lineStyle: 2, lastValueVisible: false,
          priceFormat: { type: 'custom' as const, formatter: () => '' },
        })
        rsiOversoldRef.current = chart.addSeries(LineSeries, {
          color: '#0ecb81', lineWidth: 1, lineStyle: 2, lastValueVisible: false,
          priceFormat: { type: 'custom' as const, formatter: () => '' },
        })
      }
      if (rsiSeriesRef.current && indicators?.rsi14 != null) {
        const lastTime = candleData.length > 0 ? candleData[candleData.length - 1].time : 0
        rsiSeriesRef.current.setData([{ time: lastTime as UTCTimestamp, value: indicators.rsi14 }])
        rsiOverboughtRef.current?.setData([{ time: lastTime as UTCTimestamp, value: 70 }])
        rsiOversoldRef.current?.setData([{ time: lastTime as UTCTimestamp, value: 30 }])
      }
    } else {
      if (rsiSeriesRef.current) { chart.removeSeries(rsiSeriesRef.current); rsiSeriesRef.current = null }
      if (rsiOverboughtRef.current) { chart.removeSeries(rsiOverboughtRef.current); rsiOverboughtRef.current = null }
      if (rsiOversoldRef.current) { chart.removeSeries(rsiOversoldRef.current); rsiOversoldRef.current = null }
    }

    // MACD overlay
    if (visibleIndicators.macd) {
      if (!macdLineRef.current) {
        macdLineRef.current = chart.addSeries(LineSeries, {
          color: '#FCD535', lineWidth: 1, title: 'MACD',
        })
        macdSignalRef.current = chart.addSeries(LineSeries, {
          color: '#5e7cc4', lineWidth: 1, title: 'Signal',
        })
      }
      if (macdLineRef.current && indicators?.macd != null) {
        const lastTime = candleData.length > 0 ? candleData[candleData.length - 1].time : 0
        macdLineRef.current.setData([{ time: lastTime as UTCTimestamp, value: indicators.macd }])
        macdSignalRef.current?.setData([{ time: lastTime as UTCTimestamp, value: indicators.macd_signal ?? 0 }])
      }
    } else {
      if (macdLineRef.current) { chart.removeSeries(macdLineRef.current); macdLineRef.current = null }
      if (macdSignalRef.current) { chart.removeSeries(macdSignalRef.current); macdSignalRef.current = null }
    }

    // BB overlay
    if (visibleIndicators.bb) {
      if (!bbUpperRef.current) {
        bbUpperRef.current = chart.addSeries(LineSeries, {
          color: '#FCD535', lineWidth: 1, lineStyle: 2, lastValueVisible: false, title: 'BB Upper',
        })
        bbMiddleRef.current = chart.addSeries(LineSeries, {
          color: '#FCD535', lineWidth: 1, lastValueVisible: false, title: 'BB Mid',
        })
        bbLowerRef.current = chart.addSeries(LineSeries, {
          color: '#FCD535', lineWidth: 1, lineStyle: 2, lastValueVisible: false, title: 'BB Lower',
        })
      }
      if (bbUpperRef.current && indicators?.bb_upper != null && indicators?.bb_middle != null && indicators?.bb_lower != null) {
        const lastTime = candleData.length > 0 ? candleData[candleData.length - 1].time : 0
        const uuid = lastTime as UTCTimestamp
        bbUpperRef.current.setData([{ time: uuid, value: indicators.bb_upper }])
        bbMiddleRef.current?.setData([{ time: uuid, value: indicators.bb_middle }])
        bbLowerRef.current?.setData([{ time: uuid, value: indicators.bb_lower }])
      }
    } else {
      if (bbUpperRef.current) { chart.removeSeries(bbUpperRef.current); bbUpperRef.current = null }
      if (bbMiddleRef.current) { chart.removeSeries(bbMiddleRef.current); bbMiddleRef.current = null }
      if (bbLowerRef.current) { chart.removeSeries(bbLowerRef.current); bbLowerRef.current = null }
    }

    chart.timeScale().fitContent()
  }, [candles, indicators, obs, structure, pending, visibleIndicators, chartApi])

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
            {refreshing && <LoadingSpinner size={14} />}
          </div>
          <div className="flex gap-1">
            {[{key:'rsi',label:'RSI'},{key:'macd',label:'MACD'},{key:'bb',label:'BB'}].map(t => (
              <button key={t.key}
                onClick={() => toggleIndicator(t.key)}
                className={`px-2 py-1.5 text-xs rounded border cursor-pointer transition-colors ${
                  visibleIndicators[t.key] ? 'bg-primary/10 text-primary border-primary/50' : 'bg-surface-card-dark text-muted border-hairline-on-dark hover:border-surface-elevated-dark'
                }`}
              >{t.label}</button>
            ))}
          </div>
          {/* Drawing toolbar */}
          <div className="flex items-center gap-1.5 flex-wrap">
            {(['trendline', 'horizontal', 'vertical', 'rectangle', 'ray'] as const).map(tool => (
              <button
                key={tool}
                onClick={() => { setActiveTool(activeTool === tool ? null : tool) }}
                className={`px-2.5 py-1.5 text-xs rounded-md border cursor-pointer transition-colors ${
                  activeTool === tool
                    ? 'bg-primary/10 text-primary border-primary/50'
                    : 'bg-surface-card-dark text-muted border-hairline-on-dark hover:border-surface-elevated-dark'
                }`}
              >
                {tool === 'trendline' ? '↗' : tool === 'horizontal' ? '—' : tool === 'vertical' ? '│' : tool === 'rectangle' ? '▭' : '➡'}
                <span className="ml-1 hidden sm:inline">{tool}</span>
              </button>
            ))}
            <input
              type="color"
              value={color}
              onChange={e => setColor(e.target.value)}
              className="w-6 h-6 rounded cursor-pointer border-0 p-0 bg-transparent"
              title="Color"
            />
            {drawingCount > 0 && (
              <button onClick={clearAll} className="px-2 py-1.5 text-xs rounded-md border border-hairline-on-dark bg-surface-card-dark text-muted hover:text-trading-down cursor-pointer">
                ✕ Clear
              </button>
            )}
            {selectedId && <span className="text-[10px] text-muted">R-click delete</span>}
          </div>
        </div>
      </div>

      <div className="relative rounded-lg overflow-hidden border border-hairline-on-dark">
        <div ref={chartRef} />
        <svg
          ref={overlayRef}
          className="absolute inset-0 z-10"
          style={{ pointerEvents: activeTool ? 'auto' : 'none' }}
          {...handlers}
        >
          {renderDrawings()}
          {liveSvg}
        </svg>
      </div>

      {indicators && (
        <div className="grid grid-cols-2 md:grid-cols-8 gap-3">
          <IndiCard label="MA60" value={indicators.ma60?.toFixed(2) ?? '—'} color="#FCD535" />
          <IndiCard label="MA80" value={indicators.ma80?.toFixed(2) ?? '—'} color="#5e7cc4" />
          <IndiCard label="ATR14" value={indicators.atr14?.toFixed(2) ?? '—'} color="#eaecef" />
          <IndiCard label="RSI14" value={indicators.rsi14?.toFixed(1) ?? '—'} color={indicators.rsi14 != null ? (indicators.rsi14 > 70 ? '#f6465d' : indicators.rsi14 < 30 ? '#0ecb81' : '#8c6cd8') : '#eaecef'} />
          <IndiCard label="MACD" value={indicators.macd?.toFixed(2) ?? '—'} color="#FCD535" />
          <IndiCard label="Signal" value={indicators.macd_signal?.toFixed(2) ?? '—'} color="#5e7cc4" />
          <IndiCard label="BB Mid" value={indicators.bb_middle?.toFixed(2) ?? '—'} color="#FCD535" />
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