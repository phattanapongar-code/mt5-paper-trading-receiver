import { useEffect, useRef } from 'react'
import { createChart, HistogramSeries, type IChartApi, type ISeriesApi, type HistogramData } from 'lightweight-charts'

interface PnLDistributionProps {
  data: number[]
  className?: string
}

export default function PnLDistribution({ data: pnlData, className = '' }: PnLDistributionProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const chart = useRef<IChartApi | null>(null)
  const pnlSeries = useRef<ISeriesApi<'Histogram'> | null>(null)

  useEffect(() => {
    if (!chartRef.current) return

    chart.current = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 160,
      layout: { background: { color: '#1e2329' }, textColor: '#eaecef' },
      grid: { vertLines: { color: '#2b3139' }, horzLines: { color: '#2b3139' } },
      crosshair: { vertLine: { color: '#2b3139' }, horzLine: { color: '#2b3139' } },
      timeScale: { borderColor: '#2b3139' },
      rightPriceScale: { borderColor: '#2b3139' },
    })

    pnlSeries.current = chart.current.addSeries(HistogramSeries, {
      color: '#0ecb81',
      priceFormat: { type: 'volume' },
      priceScaleId: 'pnl',
    })

    chart.current.priceScale('pnl').applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
      visible: false,
    })

    const handleResize = () => {
      if (chart.current && chartRef.current) {
        chart.current.resize(chartRef.current.clientWidth, 160)
      }
    }
    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
      chart.current?.remove()
    }
  }, [])

  useEffect(() => {
    if (!pnlSeries.current) return

    const histData: HistogramData[] = pnlData
      .filter((v) => v !== 0)
      .map((v) => ({
        time: (Date.now() / 1000) as any,
        value: v,
        color: v >= 0 ? '#0ecb81' : '#f6465d',
      }))

    if (histData.length) {
      pnlSeries.current.setData(histData)
    }
  }, [pnlData])

  if (!pnlData.length || pnlData.every((v) => v === 0)) {
    return (
      <div className={`flex items-center justify-center ${className}`}>
        <div className="text-muted text-sm font-mono py-8">No trades yet</div>
      </div>
    )
  }

  return (
    <div ref={chartRef} className={`w-full rounded-lg overflow-hidden border border-hairline-on-dark ${className}`} />
  )
}
