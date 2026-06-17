import { Handle, Position } from '@xyflow/react'

export default function ValueNode({ data }: { data: { params: { value: unknown }; label: string; color?: string } }) {
  const { params, label, color = '#78909c' } = data
  return (
    <div className="relative w-full">
      <div className="h-full px-3 py-2 bg-surface-card-dark border border-hairline-on-dark rounded-md shadow-lg" style={{ borderColor: color }}>
        <span className="text-sm font-semibold text-body block mb-1" style={{ color }}>{label}</span>
        <span className="text-xs font-mono text-body bg-surface-elevated-dark px-2 py-0.5 rounded">
          {String(params.value ?? '')}
        </span>
      </div>
      <Handle type="source" position={Position.Right} className="bg-primary" style={{ width: '8px', height: '8px', top: '50%', marginTop: '-4px' }} />
    </div>
  )
}
