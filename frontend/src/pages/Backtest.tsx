import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { createChart, LineSeries, type IChartApi, type ISeriesApi } from 'lightweight-charts'
import client from '../api/client'
import { useToast } from '../components/Toast'
import { FiPlay } from 'react-icons/fi'
import type { Bot, BacktestResult, BacktestHistory } from '../types/api'

const TIMEFRAMES = ['M1', 'M5', 'M15', 'H1'] as const

function EquityCurve({ data, height = 200 }: { data: { time: number; equity: number }[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null)

  useEffect(() => {
    if (!ref.current) return
    const chart = createChart(ref.current, {
      width: ref.current.clientWidth,
      height,
      layout: { background: { color: '#1e2329' }, textColor: '#eaecef' },
      grid: { vertLines: { color: '#2b3139' }, horzLines: { color: '#2b3139' } },
      crosshair: { vertLine: { color: '#555' }, horzLine: { color: '#555' } },
      timeScale: { borderColor: '#2b3139', visible: false },
      rightPriceScale: { borderColor: '#2b3139' },
    })
    const series = chart.addSeries(LineSeries, {
      color: '#FCD535', lineWidth: 2,
      priceFormat: { type: 'custom', formatter: (v: number) => '$' + v.toFixed(2) },
    })
    chartRef.current = chart
    seriesRef.current = series
    const resize = () => { if (ref.current) chart.resize(ref.current.clientWidth, height) }
    window.addEventListener('resize', resize)
    return () => { window.removeEventListener('resize', resize); chart.remove() }
  }, [height])

  useEffect(() => {
    if (seriesRef.current && data.length) {
      seriesRef.current.setData(data.map(d => ({ time: d.time as any, value: d.equity })))
      chartRef.current?.timeScale().fitContent()
    }
  }, [data])

  return <div ref={ref} className="w-full rounded border border-hairline-on-dark" />
}

export default function Backtest() {
  const { addToast } = useToast()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [bots, setBots] = useState<Bot[]>([])
  const [visualStrategies, setVisualStrategies] = useState<{ id: number; name: string }[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)

  const [mode, setMode] = useState<'bot' | 'custom'>('custom')
  const [botId, setBotId] = useState<number | null>(null)
  const [visualStrategyId, setVisualStrategyId] = useState<number | null>(null)
  const [parametersText, setParametersText] = useState('{}')
  const [symbol, setSymbol] = useState('XAUUSD')
  const [timeframe, setTimeframe] = useState('M15')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [initialBalance, setInitialBalance] = useState(10000)
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [history, setHistory] = useState<BacktestHistory[]>([])

  const fetchMeta = useCallback(async () => {
    try {
      const [botsRes, vsRes, histRes] = await Promise.all([
        client.get<Bot[]>('/bots'),
        client.get<{ id: number; name: string }[]>('/visual-strategies'),
        client.get<BacktestHistory[]>('/backtest/history', { params: { limit: 10 } }),
      ])
      setBots(botsRes.data)
      setVisualStrategies(vsRes.data)
      setHistory(histRes.data)
    } catch { /* ignore */ } finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchMeta() }, [fetchMeta])

  // Load result from URL ?run=ID
  useEffect(() => {
    const runId = searchParams.get('run')
    if (!runId) return
    client.get<BacktestResult>(`/backtest/runs/${runId}`).then(res => setResult(res.data)).catch(() => {})
  }, [searchParams])

  const selectedBot = useMemo(() => bots.find(b => b.id === botId), [bots, botId])
  useEffect(() => {
    if (selectedBot) {
      setVisualStrategyId(selectedBot.visual_strategy_id ?? null)
      setParametersText(JSON.stringify(selectedBot.parameters ?? {}, null, 2))
      setSymbol(selectedBot.symbol)
      setTimeframe(selectedBot.timeframe)
    }
  }, [selectedBot])

  const runBacktest = useCallback(async () => {
    let params: Record<string, unknown>
    try { params = JSON.parse(parametersText) } catch { addToast('Invalid parameters JSON', 'error'); return }
    if (!startDate || !endDate) { addToast('Select start and end dates', 'error'); return }
    const startTime = Math.floor(new Date(startDate).getTime() / 1000)
    const endTime = Math.floor(new Date(endDate).getTime() / 1000)
    if (startTime >= endTime) { addToast('Start date must be before end date', 'error'); return }
    setRunning(true)
    try {
      const res = await client.post<BacktestResult>('/backtest/run', {
        bot_id: botId, visual_strategy_id: visualStrategyId, parameters: params,
        symbol, timeframe, start_time: startTime, end_time: endTime,
        initial_balance: initialBalance,
      })
      setResult(res.data)
      addToast('Backtest completed!', 'success')
      fetchMeta()
    } catch (err: unknown) {
      addToast('Backtest failed: ' + (err instanceof Error ? err.message : String(err)), 'error')
    } finally { setRunning(false) }
  }, [botId, visualStrategyId, parametersText, symbol, timeframe, startDate, endDate, initialBalance, addToast, fetchMeta])

  const exportCsv = useCallback(() => {
    if (!result || result.trades.length === 0) return
    const header = 'side,entry,exit,stop_loss,take_profit,pnl,r_multiple,exit_reason,opened_at,closed_at'
    const rows = result.trades.map(t =>
      `${t.side},${t.entry},${t.exit ?? ''},${t.stop_loss ?? ''},${t.take_profit ?? ''},${t.pnl ?? ''},${t.r_multiple ?? ''},${t.exit_reason ?? ''},${t.opened_at ?? ''},${t.closed_at ?? ''}`
    )
    const blob = new Blob([header + '\n' + rows.join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `backtest_${Date.now()}.csv`; a.click()
    URL.revokeObjectURL(url)
  }, [result])

  if (loading) return <div className="p-6 animate-pulse text-muted text-sm font-mono">Loading...</div>

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-semibold text-body">Backtest Engine</h1>

      <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4 space-y-4">
        <div className="flex gap-2">
          <button onClick={() => { setMode('custom'); setBotId(null) }}
            className={`px-3 py-1.5 text-xs rounded-md cursor-pointer ${mode === 'custom' ? 'bg-primary/10 text-primary border border-primary/50' : 'bg-surface-elevated-dark text-muted border border-hairline-on-dark'}`}>Custom</button>
          <button onClick={() => setMode('bot')}
            className={`px-3 py-1.5 text-xs rounded-md cursor-pointer ${mode === 'bot' ? 'bg-primary/10 text-primary border border-primary/50' : 'bg-surface-elevated-dark text-muted border border-hairline-on-dark'}`}>From Bot</button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {mode === 'bot' && (
            <div>
              <label className="text-xs text-muted block mb-1">Bot</label>
              <select value={botId ?? ''} onChange={e => setBotId(e.target.value ? Number(e.target.value) : null)}
                className="w-full px-2 py-1.5 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded cursor-pointer text-body">
                <option value="">Select bot...</option>
                {bots.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </div>
          )}
          <div>
            <label className="text-xs text-muted block mb-1">Visual Strategy</label>
            <select value={visualStrategyId ?? ''} onChange={e => setVisualStrategyId(e.target.value ? Number(e.target.value) : null)}
              className="w-full px-2 py-1.5 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded cursor-pointer text-body">
              <option value="">-- None (parameters only) --</option>
              {visualStrategies.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
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
            <label className="text-xs text-muted block mb-1">Initial Balance ($)</label>
            <input type="number" value={initialBalance} onChange={e => setInitialBalance(Number(e.target.value))} min={100}
              className="w-full px-2 py-1.5 text-xs bg-surface-elevated-dark border border-hairline-on-dark rounded text-body" />
          </div>
        </div>

        <div>
          <label className="text-xs text-muted block mb-1">Parameters (JSON)</label>
          <textarea value={parametersText} onChange={e => setParametersText(e.target.value)}
            className="w-full h-24 bg-canvas-dark border border-hairline-on-dark rounded text-xs font-mono text-body p-2" />
        </div>

        <button onClick={runBacktest} disabled={running}
          className="px-4 py-2 text-xs rounded bg-primary/10 text-primary border border-primary/50 cursor-pointer disabled:opacity-50">
          <span className="inline-flex items-center gap-1.5">{running ? 'Running...' : <><FiPlay size={14} /> Run Backtest</>}</span>
        </button>
      </section>

      {result && (
        <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-body">Results</h2>
            <div className="flex gap-2">
              <button onClick={exportCsv} className="px-3 py-1.5 text-xs rounded bg-surface-elevated-dark text-muted border border-hairline-on-dark cursor-pointer">Export CSV</button>
              {result.run_id && (
                <button onClick={() => client.post(`/backtest/clone-bot/${result.run_id}`).then(() => addToast('Bot cloned!', 'success')).catch(() => addToast('Clone failed', 'error'))}
                  className="px-3 py-1.5 text-xs rounded bg-primary/10 text-primary border border-primary/50 cursor-pointer">Clone to Bot</button>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard label="Net PnL" value={`$${result.net_pnl.toFixed(2)}`} color={result.net_pnl >= 0 ? '#0ecb81' : '#f6465d'} />
            <MetricCard label="Total Trades" value={String(result.total_trades)} color="#eaecef" />
            <MetricCard label="Win Rate" value={`${(result.win_rate * 100).toFixed(1)}%`} color="#eaecef" />
            <MetricCard label="Profit Factor" value={result.profit_factor.toFixed(2)} color={result.profit_factor >= 1.5 ? '#0ecb81' : '#f6465d'} />
            <MetricCard label="Sharpe Ratio" value={result.sharpe_ratio.toFixed(2)} color={result.sharpe_ratio >= 1 ? '#0ecb81' : '#f6465d'} />
            <MetricCard label="Max DD" value={`${result.max_drawdown_pct.toFixed(1)}%`} color="#f6465d" />
            <MetricCard label="Avg R" value={result.avg_r.toFixed(2)} color={result.avg_r >= 1 ? '#0ecb81' : '#f6465d'} />
            <MetricCard label="Return" value={`${result.return_pct.toFixed(1)}%`} color={result.return_pct >= 0 ? '#0ecb81' : '#f6465d'} />
          </div>

          {result.equity_curve?.length > 0 && (
            <div>
              <p className="text-xs text-muted mb-2">Equity Curve</p>
              <EquityCurve data={result.equity_curve} height={180} />
            </div>
          )}

          {result.trades.length > 0 && (
            <div>
              <p className="text-xs text-muted mb-2">Trades (last {Math.min(result.trades.length, 100)})</p>
              <div className="overflow-x-auto max-h-64 overflow-y-auto">
                <table className="w-full text-xs">
                  <thead><tr className="border-b border-hairline-on-dark text-muted">
                    <th className="text-left p-2">Side</th><th className="text-right p-2">Entry</th><th className="text-right p-2">Exit</th>
                    <th className="text-right p-2">PnL</th><th className="text-right p-2">R</th><th className="text-left p-2">Reason</th>
                  </tr></thead>
                  <tbody>
                    {result.trades.map((t, i) => (
                      <tr key={i} className="border-b border-surface-elevated-dark">
                        <td className={`p-2 font-mono ${t.side === 'buy' ? 'text-trading-up' : 'text-trading-down'}`}>{t.side.toUpperCase()}</td>
                        <td className="p-2 font-mono text-right">{t.entry.toFixed(2)}</td>
                        <td className="p-2 font-mono text-right">{t.exit?.toFixed(2) ?? '—'}</td>
                        <td className={`p-2 font-mono text-right ${(t.pnl ?? 0) >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>{t.pnl != null ? `${t.pnl >= 0 ? '+' : ''}$${t.pnl.toFixed(2)}` : '—'}</td>
                        <td className={`p-2 font-mono text-right ${(t.r_multiple ?? 0) >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>{t.r_multiple?.toFixed(2) ?? '—'}</td>
                        <td className="p-2 text-muted">{t.exit_reason ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      )}

      {history.length > 0 && (
        <section className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <h2 className="text-sm font-semibold text-body mb-3">Recent Backtests</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="border-b border-hairline-on-dark text-muted">
                <th className="text-left p-2">Strategy</th><th className="text-left p-2">Symbol</th>
                <th className="text-right p-2">Trades</th><th className="text-right p-2">Net PnL</th>
                <th className="text-right p-2">Win Rate</th><th className="text-right p-2">PF</th>
                <th className="text-right p-2">Sharpe</th><th className="text-right p-2">DD</th>
              </tr></thead>
              <tbody>
                {history.map(h => (
                  <tr key={h.id} className="border-b border-surface-elevated-dark cursor-pointer hover:bg-surface-elevated-dark/30" onClick={() => navigate(`/backtest?run=${h.id}`)}>
                    <td className="p-2 font-mono">Visual</td>
                    <td className="p-2 font-mono">{h.symbol} {h.timeframe}</td>
                    <td className="p-2 font-mono text-right">{h.total_trades}</td>
                    <td className={`p-2 font-mono text-right ${h.net_pnl >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>${h.net_pnl.toFixed(2)}</td>
                    <td className="p-2 font-mono text-right">{(h.win_rate * 100).toFixed(0)}%</td>
                    <td className="p-2 font-mono text-right">{h.profit_factor.toFixed(2)}</td>
                    <td className="p-2 font-mono text-right">{h.sharpe_ratio.toFixed(2)}</td>
                    <td className="p-2 font-mono text-right">{h.max_drawdown_pct.toFixed(1)}%</td>
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

function MetricCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-surface-elevated-dark/50 border border-hairline-on-dark rounded-lg p-3">
      <p className="text-[10px] text-muted uppercase tracking-wider mb-1">{label}</p>
      <p className="font-mono text-sm font-semibold" style={{ color }}>{value}</p>
    </div>
  )
}
