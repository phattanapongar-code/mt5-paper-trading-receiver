import { type Node } from '@xyflow/react'

interface ConfigPanelProps {
  node: Node
  onUpdate: (nodeId: string, params: Record<string, unknown>) => void
  onClose: () => void
}

export default function ConfigPanel({ node, onUpdate, onClose }: ConfigPanelProps) {
  const d = node.data as Record<string, unknown>
  const params = (d.params as Record<string, unknown>) ?? {}
  const color = (d.color as string) ?? '#FCD535'
  const nodeLabel = (d.label as string) ?? node.type ?? ''

  const handleChange = (key: string, value: unknown) => {
    onUpdate(node.id, { ...params, [key]: value })
  }

  return (
    <div className="w-64 bg-surface-card-dark border-l border-hairline-on-dark flex flex-col">
      <div className="p-3 border-b border-hairline-on-dark flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
          <span className="text-sm font-semibold text-body">{nodeLabel}</span>
        </div>
        <button onClick={onClose} className="text-muted hover:text-body text-lg leading-none cursor-pointer">&times;</button>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-4 text-sm">
        {node.type === 'data_source' && (
          <>
            <label className="block">
              <span className="text-muted block mb-1">Symbol</span>
              <input
                type="text"
                value={(params.symbol as string) ?? ''}
                onChange={e => handleChange('symbol', e.target.value)}
                className="w-full bg-canvas-dark border border-hairline-on-dark rounded px-2 py-1 text-body"
              />
            </label>
            <label className="block">
              <span className="text-muted block mb-1">Timeframe</span>
              <select
                value={(params.timeframe as string) ?? 'M15'}
                onChange={e => handleChange('timeframe', e.target.value)}
                className="w-full bg-canvas-dark border border-hairline-on-dark rounded px-2 py-1 text-body"
              >
                {['M1','M5','M15','H1'].map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </label>
          </>
        )}
        {['sma','rsi','atr','ema'].includes(node.type ?? '') && (
          <label className="block">
            <span className="text-muted block mb-1">Period</span>
            <input
              type="number"
              value={(params.period as number) ?? 14}
              onChange={e => handleChange('period', parseInt(e.target.value) || 14)}
              className="w-full bg-canvas-dark border border-hairline-on-dark rounded px-2 py-1 text-body"
              min={1}
            />
          </label>
        )}
        {node.type === 'compare' && (
          <label className="block">
            <span className="text-muted block mb-1">Operator</span>
            <select
              value={(params.operator as string) ?? '>'}
              onChange={e => handleChange('operator', e.target.value)}
              className="w-full bg-canvas-dark border border-hairline-on-dark rounded px-2 py-1 text-body"
            >
              {['>','<','>=','<=','==','cross_above','cross_below'].map(op => (
                <option key={op} value={op}>{op}</option>
              ))}
            </select>
          </label>
        )}
        {['and','or','not'].includes(node.type ?? '') && (
          <p className="text-muted italic">No parameters required</p>
        )}
        {node.type === 'order' && (
          <>
            <label className="block">
              <span className="text-muted block mb-1">Side</span>
              <div className="flex gap-2">
                <button
                  onClick={() => handleChange('side', 'buy')}
                  className={`flex-1 px-2 py-1 rounded text-sm cursor-pointer border ${params.side === 'buy' ? 'bg-green-600/20 text-green-400 border-green-500/50' : 'bg-canvas-dark text-muted border-hairline-on-dark'}`}
                >BUY</button>
                <button
                  onClick={() => handleChange('side', 'sell')}
                  className={`flex-1 px-2 py-1 rounded text-sm cursor-pointer border ${params.side === 'sell' ? 'bg-red-600/20 text-red-400 border-red-500/50' : 'bg-canvas-dark text-muted border-hairline-on-dark'}`}
                >SELL</button>
              </div>
            </label>
            <label className="block">
              <span className="text-muted block mb-1">Risk %</span>
              <input
                type="number"
                value={(params.risk_percent as number) ?? 1}
                onChange={e => handleChange('risk_percent', parseFloat(e.target.value) || 1)}
                className="w-full bg-canvas-dark border border-hairline-on-dark rounded px-2 py-1 text-body"
                min={0.1} step={0.1}
              />
            </label>
            <label className="block">
              <span className="text-muted block mb-1">SL (ATR ×)</span>
              <input
                type="number"
                value={(params.sl_atr_multiplier as number) ?? 1.5}
                onChange={e => handleChange('sl_atr_multiplier', parseFloat(e.target.value) || 1.5)}
                className="w-full bg-canvas-dark border border-hairline-on-dark rounded px-2 py-1 text-body"
                min={0.5} step={0.1}
              />
            </label>
            <label className="block">
              <span className="text-muted block mb-1">TP (R multiple)</span>
              <input
                type="number"
                value={(params.tp_r_multiple as number) ?? 2}
                onChange={e => handleChange('tp_r_multiple', parseFloat(e.target.value) || 2)}
                className="w-full bg-canvas-dark border border-hairline-on-dark rounded px-2 py-1 text-body"
                min={1} step={0.1}
              />
            </label>
            <label className="block">
              <span className="text-muted block mb-1">ATR Period</span>
              <input
                type="number"
                value={(params.atr_period as number) ?? 14}
                onChange={e => handleChange('atr_period', parseInt(e.target.value) || 14)}
                className="w-full bg-canvas-dark border border-hairline-on-dark rounded px-2 py-1 text-body"
                min={1}
              />
            </label>
          </>
        )}
      </div>
    </div>
  )
}
