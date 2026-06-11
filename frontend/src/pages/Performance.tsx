import { useEffect, useState, useRef } from 'react'
import client from '../api/client'
import { createChart, LineSeries, HistogramSeries, type IChartApi, type ISeriesApi, type LineData, type HistogramData } from 'lightweight-charts'

export default function Performance() {
  const chartRef = useRef<HTMLDivElement>(null)
  const chart = useRef<IChartApi | null>(null)
  const equitySeries = useRef<ISeriesApi<'Line'> | null>(null)
  const pnlSeries = useRef<ISeriesApi<'Histogram'> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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

      if (!eqData.length && !pnlData.length) {
        setError('No performance data available yet.')
        setLoading(false)
        return
      }

      if (eqData.length && equitySeries.current) {
        const lineData: LineData[] = eqData
          .filter(([t]) => t > 0)
          .map(([t, v]) => ({ time: t as any, value: v }))
        if (lineData.length) equitySeries.current.setData(lineData)
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
    <div className="p-6 space-y-4">
      <h1 className="text-sm font-semibold text-body">Performance Charts</h1>
      {loading && <div className="text-muted text-xs">Loading...</div>}
      {error && <div className="text-muted text-xs">{error}</div>}
      <div ref={chartRef} className="w-full" />
    </div>
  )
}
