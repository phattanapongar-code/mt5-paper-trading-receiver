import { useState, useCallback, useEffect, useMemo } from 'react'
import client from '../api/client'
import { useToast } from '../components/Toast'
import { FiPlay, FiX } from 'react-icons/fi'
import type { OptimizeResult } from '../types/api'

const TIMEFRAMES = ['M1', 'M5', 'M15', 'H1'] as const
const METRICS = ['sharpe_ratio', 'profit_factor', 'net_pnl', 'total_r', 'win_rate'] as const

interface ParamRangeRow {
  name: string
  min: number
  max: number
  step: number
}

export default function BacktestOptimize() {
  const { addToast } = useToast()
  const [strategies, setStrategies] = useState<{ id: string; name: string }[]>([])
  const [strategyType, setStrategyType] = useState('trend_ob')
  const [symbol, setSymbol] = useState('XAUUSD')
  const [timeframe, setTimeframe] = useState('M15')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [initialBalance] = useState(10000)
  const [metric, setMetric] = useState<string>('sharpe_ratio')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<OptimizeResult | null>(null)

  const [paramRows, setParamRows] = useState<ParamRangeRow[]>([
    { name: 'risk_percent', min: 0.005, max: 0.02, step: 0.005 },
    { name: 'tp_r_multiple', min: 1.5, max: 3.0, step: 0.5 },
  ])

  const fetchMeta = useCallback(async () => {
    try {
      const res = await client.get<{ id: string; name: string }[]>('/strategies')
      setStrategies(res.data)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { fetchMeta() }, [fetchMeta])

  const addParam = useCallback(() => {
    setParamRows(prev => [...prev, { name: '', min: 0, max: 1, step: 0.1 }])
  }, [])

  const removeParam = useCallback((idx: number) => {
    setParamRows(prev => prev.filter((_, i) => i !== idx))
  }, [])

  const updateParam = useCallback((idx: number, field: keyof ParamRangeRow, value: string | number) => {
    setParamRows(prev => prev.map((r, i) => i === idx ? { ...r, [field]: typeof value === 'string' ? value : Number(value) } : r))
  }, [])

  const runOptimize = useCallback(async () => {
    const invalid = paramRows.find(r => !r.name.trim())
    if (invalid) { addToast('All params must have a name', 'error'); return }
    if (!startDate || !endDate) { addToast('Select start and end dates', 'error'); return }
    const startTime = Math.floor(new Date(startDate).getTime() / 1000)
    const endTime = Math.floor(new Date(endDate).getTime() / 1000)
    if (startTime >= endTime) { addToast('Start must be before end date', 'error'); return }

    const paramRanges: Record<string, number[]> = {}
    for (const row of paramRows) {
      const values: number[] = []
      for (let v = row.min; v <= row.max + 1e-9; v += row.step) {
        values.push(Math.round(v * 1e6) / 1e6)
      }
      paramRanges[row.name] = values
    }

    setRunning(true)
    try {
      const res = await client.post<OptimizeResult>('/backtest/optimize', {
        strategy_type: strategyType, param_ranges: paramRanges,
        symbol, timeframe, start_time: startTime, end_time: endTime,
        initial_balance: initialBalance, optimization_metric: metric,
      })
      setResult(res.data)
      addToast(`Optimization complete! ${res.data.total_combinations} combinations`, 'success')
    } catch (err: unknown) {
      addToast('Optimization failed: ' + (err instanceof Error ? err.message : String(err)), 'error')
    } finally { setRunning(false) }
  }, [strategyType, symbol, timeframe, startDate, endDate, initialBalance, metric, paramRows, addToast])

  const best = useMemo(() => {
    if (!result || result.results.length === 0) return null
    return result.results[0] as Record<string, unknown>
  }, [result])

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-body">Parameter Optimizer</h1>
        <span className="text-xs text-muted font-mono">{strategies.length} strategies</span>
      </div>

      <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="text-xs text-muted block mb-1">Strategy</label>
            <select value={strategyType} onChange={e => setStrategyType(e.target.value)}
              className="w-full px-2 py-1.5 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded cursor-pointer text-body">
              {strategies.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-muted block mb-1">Symbol</label>
            <input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())}
              className="w-full px-2 py-1.5 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded text-body" />
          </div>
          <div>
            <label className="text-xs text-muted block mb-1">Timeframe</label>
            <select value={timeframe} onChange={e => setTimeframe(e.target.value)}
              className="w-full px-2 py-1.5 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded cursor-pointer text-body">
              {TIMEFRAMES.map(tf => <option key={tf} value={tf}>{tf}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-muted block mb-1">Start Date</label>
            <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
              className="w-full px-2 py-1.5 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded text-body" />
          </div>
          <div>
            <label className="text-xs text-muted block mb-1">End Date</label>
            <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
              className="w-full px-2 py-1.5 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded text-body" />
          </div>
          <div>
            <label className="text-xs text-muted block mb-1">Optimization Metric</label>
            <select value={metric} onChange={e => setMetric(e.target.value)}
              className="w-full px-2 py-1.5 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded cursor-pointer text-body">
              {METRICS.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs text-muted">Parameter Ranges</label>
            <button onClick={addParam} className="text-xs text-primary border border-primary/50 rounded px-2 py-0.5 cursor-pointer bg-primary/10">+ Add</button>
          </div>
          <div className="space-y-2">
            {paramRows.map((row, i) => (
              <div key={i} className="flex gap-2 items-center">
                <input value={row.name} onChange={e => updateParam(i, 'name', e.target.value)}
                  placeholder="param_name"
                  className="w-28 px-2 py-1 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded text-body font-mono" />
                <input type="number" value={row.min} onChange={e => updateParam(i, 'min', e.target.value)} step="any"
                  className="w-16 px-2 py-1 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded text-body" />
                <span className="text-xs text-muted">to</span>
                <input type="number" value={row.max} onChange={e => updateParam(i, 'max', e.target.value)} step="any"
                  className="w-16 px-2 py-1 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded text-body" />
                <span className="text-xs text-muted">step</span>
                <input type="number" value={row.step} onChange={e => updateParam(i, 'step', e.target.value)} step="any"
                  className="w-16 px-2 py-1 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded text-body" />
                <button onClick={() => removeParam(i)} className="text-xs text-rose-500 px-1 cursor-pointer"><FiX size={14} /></button>
              </div>
            ))}
          </div>
        </div>

        <button onClick={runOptimize} disabled={running}
          className="px-4 py-2 text-xs rounded bg-primary/10 text-primary border border-primary/50 cursor-pointer disabled:opacity-50">
          <span className="inline-flex items-center gap-1.5">{running ? 'Optimizing...' : <><FiPlay size={14} /> Run Optimization</>}</span>
        </button>
      </section>

      {result && (
        <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4 space-y-4">
          <h2 className="text-sm font-semibold text-body">
            Results ({result.total_combinations} combos, sorted by {result.optimization_metric})
          </h2>

          {best && (
            <div className="bg-primary/5 border border-primary/30 rounded-lg p-3">
              <p className="text-xs text-primary font-semibold mb-2">Best Parameters</p>
              <div className="flex flex-wrap gap-3 text-xs font-mono">
                {Object.entries(best).filter(([k]) => !['total_trades','win_rate','net_pnl','profit_factor','sharpe_ratio','max_drawdown_pct','avg_r','total_r'].includes(k)).map(([k, v]) => (
                  <span key={k}><span className="text-muted">{k}:</span> <span className="text-body">{typeof v === 'number' ? v.toFixed(4) : String(v)}</span></span>
                ))}
              </div>
              <div className="flex gap-4 mt-2 text-xs">
                <span className="text-trading-up">Net PnL: ${(best.net_pnl as number)?.toFixed(2)}</span>
                <span>Win Rate: {((best.win_rate as number) * 100).toFixed(0)}%</span>
                <span>PF: {(best.profit_factor as number)?.toFixed(2)}</span>
                <span>Sharpe: {(best.sharpe_ratio as number)?.toFixed(2)}</span>
              </div>
            </div>
          )}

          <div className="overflow-x-auto max-h-96 overflow-y-auto">
            <table className="w-full text-xs">
              <thead><tr className="border-b border-hairline-on-dark text-muted sticky top-0 bg-surface-card-dark">
                {result.results.length > 0 && Object.keys(result.results[0] as Record<string, unknown>).map(k => (
                  <th key={k} className="text-left p-2 font-mono">{k}</th>
                ))}
              </tr></thead>
              <tbody>
                {(result.results as Record<string, unknown>[]).slice(0, 50).map((row, i) => (
                  <tr key={i} className="border-b border-surface-elevated-dark hover:bg-surface-elevated-dark/30">
                    {Object.entries(row).map(([k, v]) => (
                      <td key={k} className={`p-2 font-mono ${k === 'net_pnl' ? (Number(v) >= 0 ? 'text-trading-up' : 'text-trading-down') : ''}`}>
                        {typeof v === 'number' ? v.toFixed(4) : String(v ?? '')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}
