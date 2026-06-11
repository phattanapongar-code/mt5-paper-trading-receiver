import { useEffect, useState, useRef, useMemo } from 'react'
import client from '../api/client'
import { createChart, LineSeries, HistogramSeries, type IChartApi, type ISeriesApi, type LineData, type HistogramData } from 'lightweight-charts'

export default function Performance() {
  const chartRef = useRef<HTMLDivElement>(null)
  const chart = useRef<IChartApi | null>(null)
  const equitySeries = useRef<ISeriesApi<'Line'> | null>(null)
  const pnlSeries = useRef<ISeriesApi<'Histogram'> | null>(null)
  const drawdownSeries = useRef<ISeriesApi<'Line'> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pnlByDay, setPnlByDay] = useState<[number, number][]>([])

  useEffect(() => {
    if (!chartRef.current) return

    chart.current = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 400,
      layout: { background: { color: '#1e2329' }, textColor: '#eaecef' },
      grid: { vertLines: { color: '#2b3139' }, horzLines: { color: '#2b3139' } },
      crosshair: { vertLine: { color: '#2b3139' }, horzLine: { color: '#2b3139' } },
      timeScale: { borderColor: '#2b3139' },
      rightPriceScale: { borderColor: '#2b3139' },
    })

    equitySeries.current = chart.current.addSeries(LineSeries, {
      color: '#FCD535', lineWidth: 2, crosshairMarkerVisible: true,
      priceFormat: { type: 'custom', formatter: (v: number) => v.toFixed(2) },
    })

    drawdownSeries.current = chart.current.addSeries(LineSeries, {
      color: '#f6465d', lineWidth: 1, crosshairMarkerVisible: false,
      priceFormat: { type: 'custom', formatter: (v: number) => v.toFixed(2) },
      lineStyle: 2,
    })

    pnlSeries.current = chart.current.addSeries(HistogramSeries, {
      color: '#0ecb81', priceFormat: { type: 'volume' },
      priceScaleId: 'pnl',
    })

    chart.current.priceScale('pnl').applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
      visible: false,
    })

    const handleResize = () => {
      if (chart.current && chartRef.current) {
        chart.current.resize(chartRef.current.clientWidth, 400)
      }
    }
    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
      chart.current?.remove()
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    Promise.all([
      client.get<[number, number][]>('/stats/equity'),
      client.get<[number, number][]>('/stats/pnl-by-day'),
    ]).then(([eqRes, pnlRes]) => {
      if (cancelled) return

      const eqData = eqRes.data ?? []
      const pnlData = pnlRes.data ?? []
      setPnlByDay(pnlData)

      if (!eqData.length && !pnlData.length) {
        setError('No performance data available yet.')
        setLoading(false)
        return
      }

      if (eqData.length && equitySeries.current && drawdownSeries.current) {
        const lineData: LineData[] = eqData
          .filter(([t]) => t > 0)
          .map(([t, v]) => ({ time: t as any, value: v }))
        if (lineData.length) equitySeries.current.setData(lineData)

        // drawdown from equity peak
        let peak = 0
        const ddData: LineData[] = eqData
          .filter(([t]) => t > 0)
          .map(([t, v]) => {
            peak = Math.max(peak, v)
            const dd = peak > 0 ? ((v - peak) / peak) * 100 : 0
            return { time: t as any, value: parseFloat(dd.toFixed(2)) }
          })
        if (ddData.length) drawdownSeries.current.setData(ddData)
      }

      if (pnlData.length && pnlSeries.current) {
        const histData: HistogramData[] = pnlData
          .filter(([t]) => t > 0)
          .map(([t, v]) => ({ time: t as any, value: v, color: v >= 0 ? '#0ecb81' : '#f6465d' }))
        if (histData.length) pnlSeries.current.setData(histData)
      }

      setLoading(false)
    }).catch(() => {
      if (!cancelled) {
        setError('Failed to load performance data.')
        setLoading(false)
      }
    })

    return () => { cancelled = true }
  }, [])

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-semibold text-body">Performance Charts</h1>
      {loading && <div className="text-muted text-xs">Loading...</div>}
      {error && <div className="text-muted text-xs">{error}</div>}
      <div ref={chartRef} className="w-full rounded-lg overflow-hidden border border-hairline-on-dark" />

      {pnlByDay.length > 0 && <PnlCalendar data={pnlByDay} />}
    </div>
  )
}

function PnlCalendar({ data }: { data: [number, number][] }) {
  const byDate = useMemo(() => {
    const map = new Map<string, number>()
    for (const [ts, pnl] of data) {
      const d = new Date(ts * 1000)
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      map.set(key, (map.get(key) ?? 0) + pnl)
    }
    return map
  }, [data])

  const { year, months } = useMemo(() => {
    const now = new Date()
    const year = now.getFullYear()
    const months: { month: number; label: string; days: { day: number; pnl: number | null }[] }[] = []

    for (let m = 0; m < 12; m++) {
      const daysInMonth = new Date(year, m + 1, 0).getDate()
      const label = new Date(year, m).toLocaleString('default', { month: 'short' })
      const days = []
      for (let d = 1; d <= daysInMonth; d++) {
        const key = `${year}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
        days.push({ day: d, pnl: byDate.get(key) ?? null })
      }
      months.push({ month: m, label, days })
    }
    return { year, months }
  }, [byDate])

  const maxAbs = useMemo(() => {
    let max = 1
    for (const val of byDate.values()) {
      max = Math.max(max, Math.abs(val))
    }
    return max
  }, [byDate])

  return (
    <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
      <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">PnL Calendar {year}</h2>
      <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
        {months.map((m) => (
          <div key={m.month}>
            <p className="text-xs text-muted font-semibold mb-1">{m.label}</p>
            <div className="grid grid-cols-7 gap-0.5">
              {m.days.map((d) => {
                const intensity = d.pnl != null ? Math.min(Math.abs(d.pnl) / maxAbs, 1) : 0
                const bg = d.pnl == null ? 'bg-transparent'
                  : d.pnl > 0 ? `bg-trading-up` : `bg-trading-down`
                const opacity = d.pnl != null ? Math.max(0.15, intensity * 0.85) : 0
                return (
                  <div
                    key={d.day}
                    className="w-full aspect-square rounded-sm flex items-center justify-center"
                    style={{
                      backgroundColor: d.pnl != null ? bg : 'transparent',
                      opacity: d.pnl != null ? opacity : 0,
                    }}
                    title={d.pnl != null ? `${d.pnl >= 0 ? '+' : ''}$${d.pnl.toFixed(2)}` : undefined}
                  >
                    <span className={`text-[8px] ${d.pnl != null && intensity > 0.5 ? 'text-body' : 'text-muted'}`}>{d.day}</span>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}