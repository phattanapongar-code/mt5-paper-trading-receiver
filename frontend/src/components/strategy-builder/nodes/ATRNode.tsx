import { Handle, Position } from '@xyflow/react'

interface ATRNodeProps {
  data: {
    params: { period: number }
    label: string
    color?: string
  }
}

export default function ATRNode({ data }: { data: ATRNodeProps['data'] }) {
  const { params, label, color = '#3a414a' } = data

  return (
    <div className="relative w-full">
      <div className="h-full px-3 py-2 bg-surface-card-dark border border-hairline-on-dark rounded-md shadow-lg" style={{ borderColor: color }}>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-semibold text-body" style={{ color }}>{label}</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-xs text-muted">Period:</span>
          <span className="text-xs text-body font-mono">{params.period}</span>
        </div>
      </div>
      <Handle type="target" position={Position.Left} className="bg-primary" style={{ width: '8px', height: '8px', top: '50%', marginTop: '-4px' }} />
      <Handle type="source" position={Position.Right} className="bg-primary" style={{ width: '8px', height: '8px', top: '50%', marginTop: '-4px' }} />
    </div>
  )
}
