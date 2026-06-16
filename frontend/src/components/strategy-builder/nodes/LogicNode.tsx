import { Handle, Position } from '@xyflow/react'

interface LogicNodeProps {
  data: {
    params: Record<string, unknown>
    label: string
    type: 'and' | 'or' | 'not'
    color?: string
  }
}

export default function LogicNode({ data }: { data: LogicNodeProps['data'] }) {
  const { type, label, color = type === 'and' ? '#66bb6a' : type === 'or' ? '#ffca28' : '#ef5350' } = data

  const inputCount = type === 'not' ? 1 : 2

  return (
    <div className="relative w-full">
      <div className="h-full px-3 py-2 bg-surface-card-dark border border-hairline-on-dark rounded-md shadow-lg" style={{ borderColor: color }}>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-semibold text-body" style={{ color }}>{label}</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-xs text-muted">Type:</span>
          <span className="text-xs font-mono text-body bg-surface-elevated-dark px-2 py-0.5 rounded" style={{ borderColor: color }}>
            {type.toUpperCase()}
          </span>
        </div>
      </div>
      {Array.from({ length: inputCount }).map((_, i) => (
        <Handle key={i} type="target" position={Position.Left} className="bg-primary" style={{ width: '8px', height: '8px', top: `${30 + i * 40}%`, marginTop: '-4px' }} />
      ))}
      <Handle type="source" position={Position.Right} className="bg-primary" style={{ width: '8px', height: '8px', top: '50%', marginTop: '-4px' }} />
    </div>
  )
}
