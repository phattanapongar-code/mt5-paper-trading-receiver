import { useState } from 'react'

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

const PREMADE: PreMadeStrategy[] = [
  {
    id: 'trend_ob',
    name: 'Trend + OB',
    description: 'MA60>MA80>MA300 bullish/bearish + OB retest',
    nodes: [
      { id: 'ds', type: 'data_source', params: { timeframe: 'M15' }, position: { x: 50, y: 250 } },
      { id: 'ma60', type: 'sma', params: { period: 60 }, position: { x: 50, y: 50 } },
      { id: 'ma80', type: 'sma', params: { period: 80 }, position: { x: 50, y: 150 } },
      { id: 'ma300', type: 'sma', params: { period: 300 }, position: { x: 50, y: 350 } },
      { id: 'c1', type: 'compare', params: { operator: 'cross_above' }, position: { x: 250, y: 100 } },
      { id: 'c2', type: 'compare', params: { operator: 'cross_below' }, position: { x: 250, y: 300 } },
      { id: 'and', type: 'and', params: {}, position: { x: 450, y: 100 } },
      { id: 'buy', type: 'order', params: { side: 'buy', sl_atr_multiplier: 0.3, tp_r_multiple: 2.0 }, position: { x: 650, y: 50 } },
      { id: 'sell', type: 'order', params: { side: 'sell', sl_atr_multiplier: 0.3, tp_r_multiple: 2.0 }, position: { x: 650, y: 350 } },
    ],
    edges: [
      { id: 'e1', source: 'ds', target: 'ma60' },
      { id: 'e2', source: 'ds', target: 'ma80' },
      { id: 'e3', source: 'ds', target: 'ma300' },
      { id: 'e4', source: 'ma60', target: 'c1' },
      { id: 'e5', source: 'ma80', target: 'c1' },
      { id: 'e6', source: 'ma300', target: 'c1' },
      { id: 'e7', source: 'c1', target: 'and' },
      { id: 'e8', source: 'and', target: 'buy' },
      { id: 'e9', source: 'ma60', target: 'c2' },
      { id: 'e10', source: 'ma80', target: 'c2' },
      { id: 'e11', source: 'ma300', target: 'c2' },
      { id: 'e12', source: 'c2', target: 'sell' },
    ],
  },
  {
    id: 'bb_breakout',
    name: 'BB Breakout',
    description: 'Price breaks BB upper → buy, breaks lower → sell',
    nodes: [
      { id: 'ds', type: 'data_source', params: { timeframe: 'M15' }, position: { x: 50, y: 250 } },
      { id: 'sma20', type: 'sma', params: { period: 20 }, position: { x: 50, y: 50 } },
      { id: 'atr', type: 'atr', params: { period: 14 }, position: { x: 50, y: 150 } },
      { id: 'compare', type: 'compare', params: { operator: 'cross_above' }, position: { x: 250, y: 100 } },
      { id: 'buy', type: 'order', params: { side: 'buy', sl_atr_multiplier: 1.5, tp_r_multiple: 3.0 }, position: { x: 500, y: 50 } },
      { id: 'sell', type: 'order', params: { side: 'sell', sl_atr_multiplier: 1.5, tp_r_multiple: 3.0 }, position: { x: 500, y: 350 } },
    ],
    edges: [
      { id: 'e1', source: 'ds', target: 'sma20' },
      { id: 'e2', source: 'ds', target: 'atr' },
      { id: 'e3', source: 'sma20', target: 'compare' },
      { id: 'e4', source: 'atr', target: 'compare' },
      { id: 'e5', source: 'compare', target: 'buy' },
      { id: 'e6', source: 'compare', target: 'sell' },
    ],
  },
  {
    id: 'ma_cross',
    name: 'MA Cross',
    description: 'MA60 cross MA80 — buy above, sell below',
    nodes: [
      { id: 'ds', type: 'data_source', params: { timeframe: 'M15' }, position: { x: 50, y: 250 } },
      { id: 'ma60', type: 'sma', params: { period: 60 }, position: { x: 50, y: 50 } },
      { id: 'ma80', type: 'sma', params: { period: 80 }, position: { x: 50, y: 150 } },
      { id: 'ca', type: 'compare', params: { operator: 'cross_above' }, position: { x: 250, y: 100 } },
      { id: 'cb', type: 'compare', params: { operator: 'cross_below' }, position: { x: 250, y: 300 } },
      { id: 'buy', type: 'order', params: { side: 'buy', sl_atr_multiplier: 1.5, tp_r_multiple: 3.0 }, position: { x: 500, y: 50 } },
      { id: 'sell', type: 'order', params: { side: 'sell', sl_atr_multiplier: 1.5, tp_r_multiple: 3.0 }, position: { x: 500, y: 350 } },
    ],
    edges: [
      { id: 'e1', source: 'ds', target: 'ma60' },
      { id: 'e2', source: 'ds', target: 'ma80' },
      { id: 'e3', source: 'ma60', target: 'ca' },
      { id: 'e4', source: 'ma80', target: 'ca' },
      { id: 'e5', source: 'ma60', target: 'cb' },
      { id: 'e6', source: 'ma80', target: 'cb' },
      { id: 'e7', source: 'ca', target: 'buy' },
      { id: 'e8', source: 'cb', target: 'sell' },
    ],
  },
  {
    id: 'macd_cross',
    name: 'MACD Cross',
    description: 'MACD cross Signal — buy above, sell below',
    nodes: [
      { id: 'ds', type: 'data_source', params: { timeframe: 'M15' }, position: { x: 50, y: 250 } },
      { id: 'ema12', type: 'ema', params: { period: 12 }, position: { x: 50, y: 50 } },
      { id: 'ema26', type: 'ema', params: { period: 26 }, position: { x: 50, y: 150 } },
      { id: 'ca', type: 'compare', params: { operator: 'cross_above' }, position: { x: 250, y: 100 } },
      { id: 'cb', type: 'compare', params: { operator: 'cross_below' }, position: { x: 250, y: 300 } },
      { id: 'buy', type: 'order', params: { side: 'buy', sl_atr_multiplier: 1.5, tp_r_multiple: 3.0 }, position: { x: 500, y: 50 } },
      { id: 'sell', type: 'order', params: { side: 'sell', sl_atr_multiplier: 1.5, tp_r_multiple: 3.0 }, position: { x: 500, y: 350 } },
    ],
    edges: [
      { id: 'e1', source: 'ds', target: 'ema12' },
      { id: 'e2', source: 'ds', target: 'ema26' },
      { id: 'e3', source: 'ema12', target: 'ca' },
      { id: 'e4', source: 'ema26', target: 'ca' },
      { id: 'e5', source: 'ema12', target: 'cb' },
      { id: 'e6', source: 'ema26', target: 'cb' },
      { id: 'e7', source: 'ca', target: 'buy' },
      { id: 'e8', source: 'cb', target: 'sell' },
    ],
  },
  {
    id: 'rsi_meanrev',
    name: 'RSI MeanRev',
    description: 'RSI exits oversold → buy, exits overbought → sell',
    nodes: [
      { id: 'ds', type: 'data_source', params: { timeframe: 'M15' }, position: { x: 50, y: 250 } },
      { id: 'rsi', type: 'rsi', params: { period: 14 }, position: { x: 50, y: 50 } },
      { id: 'ca', type: 'compare', params: { operator: 'cross_above' }, position: { x: 250, y: 100 } },
      { id: 'cb', type: 'compare', params: { operator: 'cross_below' }, position: { x: 250, y: 300 } },
      { id: 'buy', type: 'order', params: { side: 'buy', sl_atr_multiplier: 1.5, tp_r_multiple: 3.0 }, position: { x: 500, y: 50 } },
      { id: 'sell', type: 'order', params: { side: 'sell', sl_atr_multiplier: 1.5, tp_r_multiple: 3.0 }, position: { x: 500, y: 350 } },
    ],
    edges: [
      { id: 'e1', source: 'ds', target: 'rsi' },
      { id: 'e2', source: 'rsi', target: 'ca' },
      { id: 'e3', source: 'rsi', target: 'cb' },
      { id: 'e4', source: 'ca', target: 'buy' },
      { id: 'e5', source: 'cb', target: 'sell' },
    ],
  },
]

interface ToolbarProps {
  onDragStart?: (type: string) => void
  onLoadStrategy?: (strategy: PreMadeStrategy) => void
}

export default function Toolbar({ onDragStart: _unused, onLoadStrategy }: ToolbarProps) {
  const [expanded, setExpanded] = useState(false)

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
          <div className="p-2 space-y-1">
            {PREMADE.map((s) => (
              <button
                key={s.id}
                onClick={() => onLoadStrategy?.(s)}
                className="w-full text-left px-3 py-2.5 bg-surface-elevated-dark border border-hairline-on-dark rounded-md cursor-pointer hover:bg-surface-card-dark transition-colors group"
              >
                <span className="text-sm font-medium text-body group-hover:text-primary transition-colors">{s.name}</span>
                <p className="text-[10px] text-muted mt-0.5 leading-tight">{s.description}</p>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
