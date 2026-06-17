import { Handle, Position } from '@xyflow/react'

export default function OBNotStaleNode({ data }: { data: { params: { max_age_candles?: number }; label: string; color?: string } }) {
  const { params, label, color = '#90a4ae' } = data
  return (
    <div className="relative w-full">
      <div className="h-full px-3 py-2 bg-surface-card-dark border border-hairline-on-dark rounded-md shadow-lg" style={{ borderColor: color }}>
        <span className="text-sm font-semibold text-body block mb-1" style={{ color }}>{label}</span>
        {params.max_age_candles != null && (
          <span className="text-xs text-muted">Max age: <span className="font-mono text-body">{params.max_age_candles}</span></span>
        )}
      </div>
      <Handle type="target" position={Position.Left} className="bg-primary" style={{ width: '8px', height: '8px', top: '50%', marginTop: '-4px' }} />
      <Handle type="source" position={Position.Right} className="bg-primary" style={{ width: '8px', height: '8px', top: '50%', marginTop: '-4px' }} />
    </div>
  )
}
