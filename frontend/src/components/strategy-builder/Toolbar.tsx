import { useState, useEffect } from 'react'
import client from '../../api/client'

export interface ToolbarNode {
  type: string
  label: string
  color: string
}

export interface PreMadeStrategy {
  id: string
  name: string
  description: string
  nodes: Array<{ id: string; type: string; params: Record<string, unknown>; position: { x: number; y: number } }>
  edges: Array<{ id: string; source: string; target: string }>
}

interface StrategyListItem {
  id: number
  name: string
  description: string
}

const NODE_ITEMS: ToolbarNode[] = [
  { type: 'data_source', label: 'Data Source', color: '#0dc5c5' },
  { type: 'sma', label: 'SMA', color: '#FCD535' },
  { type: 'rsi', label: 'RSI', color: '#845ef7' },
  { type: 'atr', label: 'ATR', color: '#3a414a' },
  { type: 'ema', label: 'EMA', color: '#d65db1' },
  { type: 'value', label: 'Value', color: '#78909c' },
  { type: 'field', label: 'Field', color: '#4db6ac' },
  { type: 'compare', label: 'Compare', color: '#0ecb81' },
  { type: 'and', label: 'AND', color: '#66bb6a' },
  { type: 'or', label: 'OR', color: '#ffca28' },
  { type: 'not', label: 'NOT', color: '#ef5350' },
  { type: 'trend', label: 'Trend', color: '#ce93d8' },
  { type: 'ob_query', label: 'OB Query', color: '#f48fb1' },
  { type: 'bollinger', label: 'Bollinger', color: '#81d4fa' },
  { type: 'macd', label: 'MACD', color: '#a5d6a7' },
  { type: 'order', label: 'Order', color: '#f6465d' },
]

interface ToolbarProps {
  onDragStart?: (type: string) => void
  onLoadStrategy?: (strategy: PreMadeStrategy) => void
}

export default function Toolbar({ onDragStart: _unused, onLoadStrategy }: ToolbarProps) {
  const [expanded, setExpanded] = useState(false)
  const [templates, setTemplates] = useState<StrategyListItem[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const fetchTemplates = async () => {
      setLoading(true)
      try {
        const res = await client.get<StrategyListItem[]>('/visual-strategies')
        setTemplates(res.data)
      } catch {
        // ignore
      } finally {
        setLoading(false)
      }
    }
    fetchTemplates()
  }, [])

  const handleLoad = async (id: number, name: string, description: string) => {
    try {
      const res = await client.get<{ graph: { nodes: any[]; edges: any[] } }>(`/visual-strategies/${id}`)
      const { graph } = res.data
      onLoadStrategy?.({
        id: String(id),
        name,
        description,
        nodes: graph.nodes,
        edges: graph.edges,
      })
    } catch {
      // ignore
    }
  }

  return (
    <div className="w-56 bg-surface-card-dark border-r border-hairline-on-dark flex flex-col">
      {/* Nodes */}
      <div className="p-3 border-b border-hairline-on-dark">
        <h2 className="text-sm font-semibold text-body">Nodes</h2>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {NODE_ITEMS.map((item) => (
          <div
            key={item.type}
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData('application/reactflow', item.type)
              e.dataTransfer.effectAllowed = 'move'
            }}
            className="flex items-center gap-3 px-3 py-2.5 bg-surface-elevated-dark border border-hairline-on-dark rounded-md cursor-move hover:bg-surface-card-dark transition-colors group"
          >
            <div
              className="w-3 h-3 rounded-full shrink-0"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-sm text-body font-medium group-hover:text-primary transition-colors">
              {item.label}
            </span>
          </div>
        ))}
      </div>

      {/* Templates section */}
      <div className="border-t border-hairline-on-dark">
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full px-3 py-2.5 flex items-center justify-between cursor-pointer hover:bg-surface-elevated-dark transition-colors"
        >
          <h2 className="text-sm font-semibold text-body">Templates</h2>
          <span className={`text-xs text-muted transition-transform ${expanded ? '' : 'rotate-[-90deg]'}`}>▾</span>
        </button>
        {expanded && (
          <div className="p-2 space-y-1 overflow-y-auto max-h-80">
            {loading ? (
              <p className="text-xs text-muted px-3 py-2">Loading...</p>
            ) : templates.length === 0 ? (
              <p className="text-xs text-muted px-3 py-2">No templates</p>
            ) : (
              templates.map((s) => (
                <button
                  key={s.id}
                  onClick={() => handleLoad(s.id, s.name, s.description)}
                  className="w-full text-left px-3 py-2.5 bg-surface-elevated-dark border border-hairline-on-dark rounded-md cursor-pointer hover:bg-surface-card-dark transition-colors group"
                >
                  <span className="text-sm font-medium text-body group-hover:text-primary transition-colors">{s.name}</span>
                  <p className="text-[10px] text-muted mt-0.5 leading-tight">{s.description}</p>
                </button>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}
