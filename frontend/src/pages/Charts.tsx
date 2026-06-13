import { useEffect, useRef, useState, useCallback } from 'react'
import { createChart, ColorType, createUpDownMarkers, type IChartApi, type ISeriesApi, type CandlestickData, type LineData, type UTCTimestamp, CandlestickSeries, LineSeries } from 'lightweight-charts'
import client from '../api/client'
import { useWebSocket } from '../api/ws'
import { useBotContext } from '../context/BotContext'
import { useDrawingTools } from '../components/DrawingTools'
import LoadingSpinner from '../components/LoadingSpinner'
import { FiEdit3, FiChevronDown, FiChevronRight, FiArrowUpRight, FiMinus, FiSquare, FiArrowRight, FiX, FiArrowUp, FiArrowDown, FiStar } from 'react-icons/fi'
import type { Candle, Indicators, OrderBlock, MarketStructureState, Trade } from '../types/api'

interface CandlePendingOrder {
  id: number; bot_id?: number; side: string; entry: number; stop_loss: number; take_profit: number
}

const TIMEFRAMES = ['M1', 'M5', 'M15', 'H1'] as const
type TF = (typeof TIMEFRAMES)[number]

const DATE_RANGES = [
  { label: '1D' as const, seconds: 86400 },
  { label: '1W' as const, seconds: 604800 },
  { label: '1M' as const, seconds: 2592000 },
  { label: '3M' as const, seconds: 7776000 },
  { label: '6M' as const, seconds: 15552000 },
  { label: '1Y' as const, seconds: 31536000 },
  { label: 'ALL' as const, seconds: 0 },
]
type DR = (typeof DATE_RANGES)[number]['label']

export default function Charts() {
  const { allBots } = useBotContext()
  const chartRef = useRef<HTMLDivElement>(null)
  const [chartApi, setChartApi] = useState<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const ma60SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma80SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma300SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const markersPluginRef = useRef<any>(null)
  const priceLinesRef = useRef<ReturnType<ISeriesApi<'Candlestick'>['createPriceLine']>[]>([])

  const [timeframe, setTimeframe] = useState<TF>('M15')
  const [dateRange, setDateRange] = useState<DR>('1W')
  const [pendingBotId, setPendingBotId] = useState<number | null>(null)
  const [candles, setCandles] = useState<Candle[]>([])
  const [indicators, setIndicators] = useState<Indicators | null>(null)
  const [obs, setObs] = useState<OrderBlock[]>([])
  const [structure, setStructure] = useState<MarketStructureState | null>(null)
  const [pending, setPending] = useState<CandlePendingOrder | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [showDrawTools, setShowDrawTools] = useState(false)
  const [trades, setTrades] = useState<Trade[]>([])
  const [candleSeries, setCandleSeries] = useState<ISeriesApi<'Candlestick'> | null>(null)
  const debounceWsRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastCandleRef = useRef<{ time: UTCTimestamp; high: number; low: number } | null>(null)

  const {
    activeTool, setActiveTool, color, setColor, selectedId, drawingCount,
    overlayRef, handlers, clearAll,
    renderDrawings, liveSvg,
  } = useDrawingTools(chartApi, chartRef as React.RefObject<HTMLDivElement | null>, candleSeries)

  const fetchData = useCallback(async (tf: TF, dr?: DR) => {
    setRefreshing(true)
    try {
      const drValue = dr ?? dateRangeRef.current
      const selected = DATE_RANGES.find(r => r.label === drValue)!
      const now = Math.floor(Date.now() / 1000)
      const candleParams: Record<string, unknown> = { limit: 50000, closed_only: false }
      if (selected.seconds > 0) {
        candleParams.start_time = now - selected.seconds
      }

      const pendingParams: Record<string, unknown> = { limit: 1 }
      if (pendingBotId) pendingParams.bot_id = pendingBotId
      const [candleRes, indRes, obRes, structRes, pendingRes] = await Promise.all([
        client.get<Candle[]>(`/candles/${tf}`, { params: candleParams }),
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

      if (pendingBotId) {
        const tr = await client.get<Trade[]>(`/bots/${pendingBotId}/trades`, { params: { limit: 50 } })
        setTrades(tr.data)
      } else {
        setTrades([])
      }
    } catch {
      // ignore
    } finally {
      setRefreshing(false)
    }
  }, [pendingBotId])

  const dateRangeRef = useRef(dateRange)
  dateRangeRef.current = dateRange

  const wsHandler = useCallback((msg: any) => {
    if (msg?.tick?.mid && candleSeriesRef.current && lastCandleRef.current) {
      const lc = lastCandleRef.current
      candleSeriesRef.current.update({
        time: lc.time,
        close: msg.tick.mid,
        high: Math.max(lc.high, msg.tick.mid),
        low: Math.min(lc.low, msg.tick.mid),
      })
    }
    if (debounceWsRef.current) clearTimeout(debounceWsRef.current)
    debounceWsRef.current = setTimeout(() => {
      fetchData(timeframeRef.current, dateRangeRef.current)
    }, 2000)
  }, [fetchData])

  const timeframeRef = useRef(timeframe)
  timeframeRef.current = timeframe
  useWebSocket('/ws/ticks', wsHandler)

  useEffect(() => {
    fetchData(timeframe, dateRange)
    const interval = setInterval(() => fetchData(timeframe, dateRange), 5000)
    return () => clearInterval(interval)
  }, [timeframe, dateRange, fetchData])

  useEffect(() => {
    if (chartApi) chartApi.timeScale().fitContent()
  }, [timeframe, dateRange, chartApi])

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
        vertLine: { color: '#555', width: 1, style: 2, labelBackgroundColor: '#555' },
        horzLine: { color: '#555', width: 1, style: 2, labelBackgroundColor: '#555' },
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
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
      title: 'MA60',
    })
    const ma80 = chart.addSeries(LineSeries, {
      color: '#5e7cc4',
      lineWidth: 1,
      lastValueVisible: false,
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
      title: 'MA80',
    })
    const ma300 = chart.addSeries(LineSeries, {
      color: '#8c6cd8',
      lineWidth: 1,
      lastValueVisible: false,
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
      title: 'MA300',
    })

    markersPluginRef.current = createUpDownMarkers(candlesSeries)

    setChartApi(chart)
    candleSeriesRef.current = candlesSeries
    setCandleSeries(candlesSeries)
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

    if (candleData.length > 0) {
      const last = candleData[candleData.length - 1]
      lastCandleRef.current = { time: last.time as UTCTimestamp, high: last.high, low: last.low }
    }

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

    // Swing point + trade markers
    const markers: { time: UTCTimestamp; value: number; sign: number }[] = []
    if (structure?.latest_swing_high?.pivot_open_time) {
      markers.push({ time: structure.latest_swing_high.pivot_open_time as UTCTimestamp, value: structure.latest_swing_high.price, sign: -1 })
    }
    if (structure?.latest_swing_low?.pivot_open_time) {
      markers.push({ time: structure.latest_swing_low.pivot_open_time as UTCTimestamp, value: structure.latest_swing_low.price, sign: 1 })
    }
    for (const t of trades) {
      if (t.opened_at) {
        markers.push({
          time: t.opened_at as UTCTimestamp,
          value: t.entry,
          sign: t.pnl != null && t.pnl > 0 ? 1 : -1,
        })
      }
    }
    if (markers.length && markersPluginRef.current) {
      markersPluginRef.current.setMarkers(markers)
    }
  }, [candles, indicators, obs, structure, pending, trades, chartApi])

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-lg font-semibold text-body">Charts</h1>
        <div className="flex gap-1 items-center flex-wrap">
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
          <div className="h-5 w-px bg-hairline-on-dark mx-1" />
          <div className="flex gap-1">
            {DATE_RANGES.map((dr) => (
              <button
                key={dr.label}
                onClick={() => setDateRange(dr.label)}
                className={`px-2 py-1.5 text-xs font-mono rounded-md transition-colors cursor-pointer ${
                  dateRange === dr.label
                    ? 'bg-primary/10 text-primary border border-primary/50'
                    : 'bg-surface-card-dark text-muted border border-hairline-on-dark hover:border-surface-elevated-dark'
                }`}
              >
                {dr.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => setShowDrawTools(!showDrawTools)}
            className={`px-2.5 py-1.5 text-xs rounded-md border cursor-pointer transition-colors ${
              showDrawTools ? 'bg-primary/10 text-primary border-primary/50' : 'bg-surface-card-dark text-muted border-hairline-on-dark hover:border-surface-elevated-dark'
            }`}
          >
            <FiEdit3 size={14} /> Draw {showDrawTools ? <FiChevronDown size={14} /> : <FiChevronRight size={14} />}
          </button>
          {showDrawTools && (
            <div className="flex items-center gap-1.5 flex-wrap">
              {(['trendline', 'horizontal', 'vertical', 'rectangle', 'ray'] as const).map(tool => (
                <button
                  key={tool}
                  onClick={() => { setActiveTool(activeTool === tool ? null : tool) }}
                  className={`px-2 py-1.5 text-xs rounded-md border cursor-pointer transition-colors ${
                    activeTool === tool
                      ? 'bg-primary/10 text-primary border-primary/50'
                      : 'bg-surface-card-dark text-muted border-hairline-on-dark hover:border-surface-elevated-dark'
                  }`}
                >
                  {tool === 'trendline' ? <FiArrowUpRight size={14} /> : tool === 'horizontal' ? <FiMinus size={14} /> : tool === 'vertical' ? <span className="w-px h-4 bg-current inline-block" /> : tool === 'rectangle' ? <FiSquare size={14} /> : <FiArrowRight size={14} />}
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
                  <FiX size={14} /> Clear
                </button>
              )}
              {selectedId && <span className="text-[10px] text-muted">R-click delete</span>}
            </div>
          )}
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
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <IndiCard label="RSI14" value={indicators.rsi14?.toFixed(1) ?? '—'} color={indicators.rsi14 != null ? (indicators.rsi14 > 70 ? '#f6465d' : indicators.rsi14 < 30 ? '#0ecb81' : '#8c6cd8') : '#eaecef'} />
          <IndiCard label="MACD" value={indicators.macd?.toFixed(2) ?? '—'} color="#FCD535" />
          <IndiCard label="ATR14" value={indicators.atr14?.toFixed(2) ?? '—'} color="#eaecef" />
          <IndiCard label="BB Mid" value={indicators.bb_middle?.toFixed(2) ?? '—'} color="#FCD535" />
          <IndiCard
            label="Trend"
            value={indicators.trend ?? '—'}
            color={indicators.trend === 'BULLISH' ? '#0ecb81' : indicators.trend === 'BEARISH' ? '#f6465d' : '#eaecef'}
          />
        </div>
      )}

      {obs.length > 0 && (
        <div className="flex items-center gap-2 text-xs text-muted">
          <span>{obs.length} active OBs</span>
          <span className="text-trading-up inline-flex items-center gap-0.5"><FiArrowUp size={12} /> {obs.filter(o => o.side === 'buy').length}</span>
          <span className="text-trading-down inline-flex items-center gap-0.5"><FiArrowDown size={12} /> {obs.filter(o => o.side === 'sell').length}</span>
          <span className="text-primary inline-flex items-center gap-0.5"><FiStar size={12} fill="currentColor" /> {obs.filter(o => o.is_strong).length} strong</span>
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