import { Handle, Position } from '@xyflow/react'

interface OrderNodeProps {
  data: {
    params: {
      side: 'buy' | 'sell'
      risk_percent: number
      sl_atr_multiplier: number
      tp_r_multiple: number
      atr_period: number
    }
    label: string
    color?: string
  }
}

export default function OrderNode({ data }: { data: OrderNodeProps['data'] }) {
  const { params, label, color = '#f6465d' } = data

  return (
    <div className="relative w-full">
      <div className="h-full px-3 py-2 bg-surface-card-dark border border-hairline-on-dark rounded-md shadow-lg" style={{ borderColor: color }}>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-semibold text-body" style={{ color }}>{label}</span>
        </div>
        <div className="space-y-1">
          <div className="flex items-center gap-1">
            <span className="text-xs text-muted">Side:</span>
            <span className={`text-xs font-mono px-2 py-0.5 rounded ${params.side === 'buy' ? 'bg-trading-up/20 text-trading-up' : 'bg-trading-down/20 text-trading-down'}`} style={{ borderColor: color }}>
              {params.side.toUpperCase()}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-xs text-muted">Risk:</span>
            <span className="text-xs text-body font-mono">{params.risk_percent}%</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-xs text-muted">SL:</span>
            <span className="text-xs text-body font-mono">{params.sl_atr_multiplier}x ATR</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-xs text-muted">TP:</span>
            <span className="text-xs text-body font-mono">{params.tp_r_multiple}R</span>
          </div>
        </div>
      </div>
      <Handle type="target" position={Position.Left} className="bg-primary" style={{ width: '8px', height: '8px', top: '50%', marginTop: '-4px' }} />
    </div>
  )
}
