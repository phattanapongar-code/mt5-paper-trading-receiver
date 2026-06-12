import { useEffect, useRef, useState } from 'react'
import client from '../api/client'
import { createChart, LineSeries, type IChartApi, type ISeriesApi, type LineData } from 'lightweight-charts'

interface EquityChartProps {
  className?: string
  height?: number
  botId?: number
}

export default function EquityChart({ className = '', height = 300, botId }: EquityChartProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const chart = useRef<IChartApi | null>(null)
  const equitySeries = useRef<ISeriesApi<'Line'> | null>(null)
  const drawdownSeries = useRef<ISeriesApi<'Line'> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hasData, setHasData] = useState(false)

  useEffect(() => {
    if (!chartRef.current) return

    chart.current = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: height,
      layout: { background: { color: '#1e2329' }, textColor: '#eaecef' },
      grid: { vertLines: { color: '#2b3139' }, horzLines: { color: '#2b3139' } },
      crosshair: { vertLine: { color: '#2b3139' }, horzLine: { color: '#2b3139' } },
      timeScale: { borderColor: '#2b3139' },
      rightPriceScale: { borderColor: '#2b3139' },
    })

    equitySeries.current = chart.current.addSeries(LineSeries, {
      color: '#FCD535',
      lineWidth: 2,
      crosshairMarkerVisible: true,
      priceFormat: { type: 'custom', formatter: (v: number) => v.toFixed(2) },
    })

    drawdownSeries.current = chart.current.addSeries(LineSeries, {
      color: '#f6465d',
      lineWidth: 1,
      crosshairMarkerVisible: false,
      priceFormat: { type: 'custom', formatter: (v: number) => v.toFixed(2) },
      lineStyle: 2,
    })

    const handleResize = () => {
      if (chart.current && chartRef.current) {
        chart.current.resize(chartRef.current.clientWidth, height)
      }
    }
    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
      chart.current?.remove()
    }
  }, [height])

  useEffect(() => {
    if (!botId) {
      setLoading(false)
      setError(null)
      setHasData(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)

    client.get<[number, number][]>(`/bots/${botId}/stats/equity`).then((res) => {
      if (cancelled) return

      const eqData = res.data ?? []

      if (!eqData.length) {
        setError('No equity data available yet.')
        setHasData(false)
        setLoading(false)
        return
      }

      if (equitySeries.current && drawdownSeries.current) {
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

      setHasData(true)
      setLoading(false)
    }).catch(() => {
      if (!cancelled) {
        setError('Failed to load equity data.')
        setHasData(false)
        setLoading(false)
      }
    })

    return () => { cancelled = true }
  }, [botId])

  if (loading && !hasData) {
    return (
      <div className={`flex items-center justify-center ${className}`}>
        <div className="animate-pulse text-muted text-sm font-mono">Loading equity curve...</div>
      </div>
    )
  }

  if (error && !hasData) {
    return (
      <div className={`flex items-center justify-center ${className}`}>
        <div className="text-muted text-sm font-mono">{error}</div>
      </div>
    )
  }

  return (
    <div ref={chartRef} className={`w-full rounded-lg overflow-hidden border border-hairline-on-dark ${className}`} />
  )
}
