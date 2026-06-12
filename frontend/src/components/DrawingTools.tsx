import { useState, useRef, useCallback, useEffect } from 'react'
import type { IChartApi, Time } from 'lightweight-charts'

export type Tool = 'trendline' | 'horizontal' | 'vertical' | 'rectangle' | 'ray' | null

export interface Point {
  time: Time
  price: number
}

export interface Drawing {
  id: string
  type: Exclude<Tool, null>
  points: Point[]
  color: string
}

const COLORS = ['#FCD535', '#0ecb81', '#f6465d', '#5e7cc4', '#8c6cd8', '#ff8c00', '#ff69b4']
let nextId = 0

export function useDrawingTools(chartApi: IChartApi | null, containerRef: React.RefObject<HTMLDivElement | null>) {
  const [activeTool, setActiveTool] = useState<Tool>(null)
  const [color, setColor] = useState(COLORS[0])
  const [drawings, setDrawings] = useState<Drawing[]>([])
  const [liveDrawing, setLiveDrawing] = useState<Drawing | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const overlayRef = useRef<SVGSVGElement>(null)

  const toPixel = useCallback((time: Time, price: number) => {
    if (!chartApi) return { x: 0, y: 0 }
    const x = chartApi.timeScale().timeToCoordinate(time)
    const y = chartApi.priceScale().priceToCoordinate(price)
    return { x: x ?? 0, y: y ?? 0 }
  }, [chartApi])

  const toData = useCallback((clientX: number, clientY: number): Point | null => {
    if (!chartApi || !containerRef.current) return null
    const rect = containerRef.current.getBoundingClientRect()
    const x = clientX - rect.left
    const y = clientY - rect.top
    const time = chartApi.timeScale().coordinateToTime(x)
    const price = chartApi.priceScale().coordinateToPrice(y)
    if (time == null || price == null) return null
    return { time, price }
  }, [chartApi, containerRef])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (!activeTool || e.button !== 0) return
    const pt = toData(e.clientX, e.clientY)
    if (!pt) return
    const id = String(++nextId)
    if (activeTool === 'horizontal' || activeTool === 'vertical') {
      setDrawings(d => [...d, { id, type: activeTool, points: [pt], color }])
      setActiveTool(null)
    } else {
      setLiveDrawing({ id, type: activeTool, points: [pt], color })
    }
    setSelectedId(null)
  }, [activeTool, color, toData])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!liveDrawing) return
    const pt = toData(e.clientX, e.clientY)
    if (!pt) return
    setLiveDrawing(d => d ? { ...d, points: [d.points[0], pt] } : null)
  }, [liveDrawing, toData])

  const handleMouseUp = useCallback(() => {
    if (!liveDrawing) return
    if (liveDrawing.points.length >= 2) {
      setDrawings(d => [...d, liveDrawing])
    }
    setLiveDrawing(null)
  }, [liveDrawing])

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    if (!selectedId) return
    e.preventDefault()
    setDrawings(d => d.filter(dw => dw.id !== selectedId))
    setSelectedId(null)
  }, [selectedId])

  const handleClick = useCallback((e: React.MouseEvent) => {
    if (activeTool) return
    const target = e.target as SVGElement
    const g = target.closest('g[data-draw-id]') as SVGGElement | null
    setSelectedId(g?.dataset.drawId ?? null)
  }, [activeTool])

  const clearAll = useCallback(() => { setDrawings([]); setSelectedId(null) }, [])

  // Force re-render on resize
  const [, setTick] = useState(0)
  useEffect(() => {
    const handler = () => setTick(t => t + 1)
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])

  function toSvg(d: Drawing) {
    const sel = d.id === selectedId
    const sw = sel ? 3 : 1.5
    const pts = d.points

    if (d.type === 'horizontal') {
      const { y } = toPixel(pts[0].time, pts[0].price)
      return <line x1={0} x2="100%" y1={y} y2={y} stroke={d.color} strokeWidth={sw} />
    }
    if (d.type === 'vertical') {
      const { x } = toPixel(pts[0].time, pts[0].price)
      return <line x1={x} x2={x} y1={0} y2="100%" stroke={d.color} strokeWidth={sw} />
    }
    if ((d.type === 'trendline' || d.type === 'ray') && pts.length >= 2) {
      const p0 = toPixel(pts[0].time, pts[0].price)
      const p1 = toPixel(pts[1].time, pts[1].price)
      if (d.type === 'ray') {
        const dx = p1.x - p0.x
        const dy = p1.y - p0.y
        if (dx === 0) return null
        const svgW = overlayRef.current?.clientWidth ?? 1000
        const t = (svgW - p0.x) / dx
        const endX = p0.x + dx * Math.max(t, 1)
        const endY = p0.y + dy * Math.max(t, 1)
        return <line x1={p0.x} y1={p0.y} x2={endX} y2={endY} stroke={d.color} strokeWidth={sw} />
      }
      return <line x1={p0.x} y1={p0.y} x2={p1.x} y2={p1.y} stroke={d.color} strokeWidth={sw} />
    }
    if (d.type === 'rectangle' && pts.length >= 2) {
      const p0 = toPixel(pts[0].time, pts[0].price)
      const p1 = toPixel(pts[1].time, pts[1].price)
      const x = Math.min(p0.x, p1.x)
      const y = Math.min(p0.y, p1.y)
      const w = Math.abs(p1.x - p0.x)
      const h = Math.abs(p1.y - p0.y)
      return <rect x={x} y={y} width={w} height={h} stroke={d.color} strokeWidth={sw} fill={`${d.color}11`} />
    }
    return null
  }

  const renderDrawings = () => drawings.map(d => (
    <g key={d.id} data-draw-id={d.id} style={{ cursor: 'pointer' }}>
      {toSvg(d)}
      {d.id === selectedId && d.points.map((pt, i) => {
        const { x, y } = toPixel(pt.time, pt.price)
        return <circle key={i} cx={x} cy={y} r={4} fill={d.color} stroke="#fff" strokeWidth={1.5} />
      })}
    </g>
  ))

  return {
    activeTool,
    setActiveTool,
    color,
    setColor,
    selectedId,
    drawingCount: drawings.length,
    overlayRef,
    handlers: {
      onMouseDown: handleMouseDown,
      onMouseMove: handleMouseMove,
      onMouseUp: handleMouseUp,
      onClick: handleClick,
      onContextMenu: handleContextMenu,
    },
    clearAll,
    renderDrawings,
    liveSvg: liveDrawing ? toSvg(liveDrawing) : null,
  }
}
