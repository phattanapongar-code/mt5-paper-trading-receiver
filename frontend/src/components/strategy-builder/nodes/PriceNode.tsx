import { Handle, Position } from '@xyflow/react'

export default function PriceNode({ data }: { data: { params: { value: string }; label: string; color?: string } }) {
  const { params, label, color = '#ff8a65' } = data
  return (
    <div className="relative w-full">
      <div className="h-full px-3 py-2 bg-surface-card-dark border border-hairline-on-dark rounded-md shadow-lg" style={{ borderColor: color }}>
        <span className="text-sm font-semibold text-body block mb-1" style={{ color }}>{label}</span>
        <span className="text-xs text-muted">Value: <span className="font-mono text-body">{params.value}</span></span>
      </div>
      <Handle type="source" position={Position.Right} className="bg-primary" style={{ width: '8px', height: '8px', top: '50%', marginTop: '-4px' }} />
    </div>
  )
}
