import { Handle, Position } from '@xyflow/react'

export default function OBQueryNode({ data }: { data: { params: { side: string; min_score?: number }; label: string; color?: string } }) {
  const { params, label, color = '#f48fb1' } = data
  return (
    <div className="relative w-full">
      <div className="h-full px-3 py-2 bg-surface-card-dark border border-hairline-on-dark rounded-md shadow-lg" style={{ borderColor: color }}>
        <span className="text-sm font-semibold text-body block mb-1" style={{ color }}>{label}</span>
        <span className="text-xs text-muted">Side: <span className="font-mono text-body">{params.side}</span></span>
        {params.min_score != null && (
          <span className="text-xs text-muted ml-2">Score≥{params.min_score}</span>
        )}
      </div>
      <Handle type="source" position={Position.Right} className="bg-primary" style={{ width: '8px', height: '8px', top: '50%', marginTop: '-4px' }} />
    </div>
  )
}
