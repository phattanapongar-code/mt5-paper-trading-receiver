export interface ToolbarNode {
  type: string
  label: string
  color: string
}

const NODE_ITEMS: ToolbarNode[] = [
  { type: 'data_source', label: 'Data Source', color: '#0dc5c5' },
  { type: 'sma', label: 'SMA', color: '#FCD535' },
  { type: 'rsi', label: 'RSI', color: '#845ef7' },
  { type: 'atr', label: 'ATR', color: '#3a414a' },
  { type: 'ema', label: 'EMA', color: '#d65db1' },
  { type: 'compare', label: 'Compare', color: '#0ecb81' },
  { type: 'and', label: 'AND', color: '#66bb6a' },
  { type: 'or', label: 'OR', color: '#ffca28' },
  { type: 'not', label: 'NOT', color: '#ef5350' },
  { type: 'order', label: 'Order', color: '#f6465d' },
]

interface ToolbarProps {
  onDragStart: (type: string) => void
}

export default function Toolbar({ onDragStart }: ToolbarProps) {
  return (
    <div className="w-56 bg-surface-card-dark border-r border-hairline-on-dark flex flex-col">
      <div className="p-3 border-b border-hairline-on-dark">
        <h2 className="text-sm font-semibold text-body">Nodes</h2>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {NODE_ITEMS.map((item) => (
          <div
            key={item.type}
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData('application/json', JSON.stringify({ type: item.type }))
              e.dataTransfer.effectAllowed = 'move'
              onDragStart(item.type)
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
    </div>
  )
}
