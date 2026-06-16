import { Handle, Position } from '@xyflow/react'

interface CompareNodeProps {
  data: {
    params: { operator: string }
    label: string
    color?: string
  }
}

export default function CompareNode({ data }: { data: CompareNodeProps['data'] }) {
  const { params, label, color = '#0ecb81' } = data

  return (
    <div className="relative w-full">
      <div className="h-full px-3 py-2 bg-surface-card-dark border border-hairline-on-dark rounded-md shadow-lg" style={{ borderColor: color }}>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-semibold text-body" style={{ color }}>{label}</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-xs text-muted">Operator:</span>
          <span className="text-xs font-mono text-body bg-surface-elevated-dark px-2 py-0.5 rounded" style={{ borderColor: color }}>
            {params.operator}
          </span>
        </div>
      </div>
      <Handle type="target" position={Position.Left} className="bg-primary" style={{ width: '8px', height: '8px', top: '30%', marginTop: '-4px' }} />
      <Handle type="target" position={Position.Left} className="bg-primary" style={{ width: '8px', height: '8px', top: '70%', marginTop: '-4px' }} />
      <Handle type="source" position={Position.Right} className="bg-primary" style={{ width: '8px', height: '8px', top: '50%', marginTop: '-4px' }} />
    </div>
  )
}
