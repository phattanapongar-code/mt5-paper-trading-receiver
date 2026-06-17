import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import client from '../api/client'
import { useToast } from '../components/Toast'
import type { BotState, Wallet, Trade, BotSignalLog, BotStats, BotCosts } from '../types/api'

type Tab = 'info' | 'signals' | 'costs'

export default function BotDetail() {
  const { botId } = useParams()
  const navigate = useNavigate()
  const { addToast } = useToast()
  const [state, setState] = useState<BotState | null>(null)
  const [wallet, setWallet] = useState<Wallet | null>(null)
  const [trades, setTrades] = useState<Trade[]>([])
  const [signals, setSignals] = useState<BotSignalLog[]>([])
  const [costs, setCosts] = useState<BotCosts | null>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<Tab>('info')
  const [paramsText, setParamsText] = useState('')
  const [editName, setEditName] = useState('')
  const [editSymbol, setEditSymbol] = useState('')
  const [editTf, setEditTf] = useState('')
  const [cloneName, setCloneName] = useState('')
  const [showCloneModal, setShowCloneModal] = useState(false)
  const [symbols, setSymbols] = useState<string[]>([])
  const [alertChatId, setAlertChatId] = useState('')

  const botStats: BotStats = useMemo(() => {
    const closed = trades.filter(t => t.status === 'closed')
    const wins = closed.filter(t => (t.pnl ?? 0) > 0)
    const losses = closed.filter(t => (t.pnl ?? 0) < 0)
    const netPnl = closed.reduce((sum, t) => sum + (t.pnl ?? 0), 0)
    // Trades are sorted DESC (newest first) from the API.
    // Reverse to chronological order for correct drawdown calculation.
    let maxDrawdown = 0
    let cumulative = 0
    let peak = 0
    for (const t of [...trades].reverse()) {
      cumulative += (t.pnl ?? 0)
      peak = Math.max(peak, cumulative)
      maxDrawdown = Math.max(maxDrawdown, peak - cumulative)
    }
    return {
      closed_trades: closed.length,
      wins: wins.length,
      losses: losses.length,
      win_rate: closed.length > 0 ? wins.length / closed.length : 0,
      net_pnl: netPnl,
      max_drawdown_usd: maxDrawdown,
    }
  }, [trades])

  const parsedParams = useMemo(() => {
    try { return JSON.parse(paramsText) as Record<string, any> }
    catch { return {} as Record<string, any> }
  }, [paramsText])

  const fetchData = useCallback(async () => {
    try {
      const [stateRes, walletRes, tradesRes, signalsRes, costsRes, alertChatRes] = await Promise.all([
        client.get<BotState>(`/bots/${botId}/state`),
        client.get<Wallet>(`/bots/${botId}/wallet`),
        client.get<Trade[]>(`/bots/${botId}/trades`, { params: { limit: 20 } }),
        client.get<BotSignalLog[]>(`/bots/${botId}/signals`, { params: { limit: 50 } }),
        client.get<BotCosts>(`/bots/${botId}/costs`).catch(() => null),
        client.get<{ chat_id: string }>(`/bots/${botId}/alert-chat`).catch(() => null),
      ])
      setState(stateRes.data)
      setWallet(walletRes.data)
      setTrades(tradesRes.data)
      setSignals(signalsRes.data)
      if (costsRes?.data) setCosts(costsRes.data)
      if (alertChatRes?.data) setAlertChatId(alertChatRes.data.chat_id)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [botId])

  useEffect(() => {
    fetchData()
    client.get<{ symbols: string[] }>('/symbols').then(res => {
      if (res.data.symbols?.length) setSymbols(res.data.symbols)
    }).catch(() => {})
    const interval = setInterval(fetchData, 3000)
    return () => clearInterval(interval)
  }, [fetchData])

  useEffect(() => {
    if (state?.bot) {
      setParamsText(JSON.stringify(state.bot.parameters, null, 2))
      setEditName(state.bot.name)
      setEditSymbol(state.bot.symbol)
      setEditTf(state.bot.timeframe)
    }
  }, [state?.bot])

  const toggleBot = useCallback(async (enabled: boolean) => {
    await client.post(`/bots/${botId}/${enabled ? 'enable' : 'disable'}`)
    fetchData()
  }, [botId, fetchData])

  const resetWallet = useCallback(async () => {
    const balance = prompt('New balance:')
    if (balance) {
      await client.post(`/bots/${botId}/wallet/reset`, { balance: parseFloat(balance) })
      addToast('Wallet reset', 'success')
      fetchData()
    }
  }, [botId, fetchData, addToast])

  const saveEdit = useCallback(async () => {
    await client.put(`/bots/${botId}`, { name: editName, symbol: editSymbol, timeframe: editTf })
    setTab('info')
    addToast('Bot updated', 'success')
    fetchData()
  }, [botId, editName, editSymbol, editTf, fetchData, addToast])

  const openCloneModal = useCallback(() => {
    setCloneName((state?.bot?.name ?? '') + ' (clone)')
    setShowCloneModal(true)
  }, [state])

  const doClone = useCallback(async () => {
    if (!cloneName || !state) return
    await client.post('/bots', {
      profile_id: state.bot.profile_id,
      name: cloneName,
      visual_strategy_id: state.bot.visual_strategy_id,
      symbol: state.bot.symbol,
      timeframe: state.bot.timeframe,
      enabled: false,
      initial_balance: wallet?.initial_balance ?? 500,
      parameters: state.bot.parameters,
    })
    addToast('Bot cloned!', 'success')
    setShowCloneModal(false)
    navigate('/bots')
  }, [cloneName, state, wallet, navigate, addToast])

  const saveParams = useCallback(async () => {
    try {
      const parsed = JSON.parse(paramsText)
      await client.put(`/bots/${botId}/parameters`, { parameters: parsed })
      addToast('Parameters saved!', 'success')
    } catch {
      addToast('Invalid JSON', 'error')
    }
  }, [botId, paramsText, addToast])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-muted text-sm font-mono">Loading...</div>
      </div>
    )
  }

  if (!state) {
    return (
      <div className="p-6">
        <button onClick={() => navigate('/bots')} className="text-body text-sm mb-4 cursor-pointer">&larr; Back</button>
        <p className="text-muted text-sm">Bot not found</p>
      </div>
    )
  }

  const bot = state.bot

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/bots')} className="text-muted hover:text-body text-sm cursor-pointer">&larr;</button>
          <h1 className="text-lg font-semibold text-body">{bot.name}</h1>
          <span className="text-xs font-mono text-muted">Visual</span>
          <span className="text-xs font-mono text-muted">{bot.symbol} {bot.timeframe}</span>
        </div>
        <div className="flex gap-2">
          <button onClick={openCloneModal} className="px-3 py-1.5 text-xs rounded-md bg-surface-elevated-dark text-muted hover:text-body border border-hairline-on-dark cursor-pointer">Clone</button>
          <button onClick={() => toggleBot(!bot.enabled)}
            className={`px-3 py-1.5 text-xs rounded-md font-semibold transition-colors cursor-pointer ${
              bot.enabled
                ? 'bg-trading-up/10 text-trading-up border border-trading-up/50'
                : 'bg-surface-elevated-dark text-muted border border-surface-400'
            }`}>
            {bot.enabled ? 'ENABLED' : 'DISABLED'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <p className="text-xs text-muted mb-1">Wallet Balance</p>
          <p className="font-mono text-xl font-semibold text-primary">
            ${wallet?.balance.toFixed(2) ?? '—'}
          </p>
          <p className="text-xs text-muted mt-1">
            Initial: ${wallet?.initial_balance.toFixed(2) ?? '—'}
          </p>
        </div>
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <p className="text-xs text-muted mb-1">Realized PnL</p>
          <p className={`font-mono text-xl font-semibold ${(wallet?.realized_pnl ?? 0) >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>
            {(wallet?.realized_pnl ?? 0) >= 0 ? '+' : ''}${wallet?.realized_pnl.toFixed(2) ?? '—'}
          </p>
        </div>
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <p className="text-xs text-muted mb-1">Runtime</p>
          <div className="space-y-1">
            <p className="text-xs font-mono">
              <span className="text-muted">Trend: </span>
              <span className={state.runtime?.latest_trend === 'BULLISH' ? 'text-trading-up' : state.runtime?.latest_trend === 'BEARISH' ? 'text-trading-down' : 'text-muted'}>
                {state.runtime?.latest_trend ?? '—'}
              </span>
            </p>
            <p className="text-xs font-mono">
              <span className="text-muted">Consecutive Losses: </span>
              <span className={state.runtime && state.runtime.consecutive_losses > 0 ? 'text-trading-down' : 'text-trading-up'}>
                {state.runtime?.consecutive_losses ?? '—'}
              </span>
            </p>
            <p className="text-xs font-mono">
              <span className="text-muted">Daily PnL: </span>
              <span className={(state.runtime?.daily_realized_pnl ?? 0) >= 0 ? 'text-trading-up' : 'text-trading-down'}>
                ${state.runtime?.daily_realized_pnl.toFixed(2) ?? '—'}
              </span>
            </p>
          </div>
        </div>
      </div>

      <div className="flex gap-2">
        <button onClick={resetWallet} className="px-3 py-1.5 text-xs rounded-md bg-surface-elevated-dark text-text-secondary hover:text-body border border-hairline-on-dark transition-colors cursor-pointer">Reset Wallet</button>
        <button onClick={() => navigate('/backtest')} className="px-3 py-1.5 text-xs rounded-md bg-primary/10 text-primary border border-primary/50 cursor-pointer">Backtest</button>
      </div>

      {state.position && (
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Open Position</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
            <div><span className="text-muted text-xs">Side</span>
              <p className={`font-mono font-semibold ${state.position.side === 'buy' ? 'text-trading-up' : 'text-trading-down'}`}>{state.position.side.toUpperCase()}</p></div>
            <div><span className="text-muted text-xs">Lot</span><p className="font-mono">{state.position.lot}</p></div>
            <div><span className="text-muted text-xs">Entry</span><p className="font-mono">{state.position.entry.toFixed(2)}</p></div>
            <div><span className="text-muted text-xs">SL</span><p className="font-mono">{state.position.stop_loss?.toFixed(2) ?? '—'}</p></div>
            <div><span className="text-muted text-xs">TP</span><p className="font-mono">{state.position.take_profit?.toFixed(2) ?? '—'}</p></div>
          </div>
        </div>
      )}

      {state.pending && (
        <div className="bg-surface-card-dark border border-primary/30 rounded-lg p-4">
          <h2 className="text-xs font-semibold text-primary uppercase tracking-wider mb-3">Pending Order</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div><span className="text-muted text-xs">Side</span>
              <p className={`font-mono text-sm font-semibold ${state.pending.side === 'buy' ? 'text-trading-up' : 'text-trading-down'}`}>{state.pending.side.toUpperCase()}</p></div>
            <div><span className="text-muted text-xs">Entry</span><p className="font-mono text-sm">{state.pending.entry.toFixed(2)}</p></div>
            <div><span className="text-muted text-xs">SL</span><p className="font-mono text-sm">{state.pending.stop_loss.toFixed(2)}</p></div>
            <div><span className="text-muted text-xs">TP</span><p className="font-mono text-sm">{state.pending.take_profit.toFixed(2)}</p></div>
            <div><span className="text-muted text-xs">RR</span><p className="font-mono text-sm text-primary">{state.pending.risk_reward.toFixed(2)}</p></div>
          </div>
        </div>
      )}

      <div className="flex gap-4 border-b border-hairline-on-dark">
        <button onClick={() => setTab('info')} className={`pb-2 text-xs font-semibold uppercase tracking-wider cursor-pointer ${tab === 'info' ? 'text-primary border-b-2 border-primary' : 'text-muted'}`}>Info</button>
        <button onClick={() => setTab('signals')} className={`pb-2 text-xs font-semibold uppercase tracking-wider cursor-pointer ${tab === 'signals' ? 'text-primary border-b-2 border-primary' : 'text-muted'}`}>Signal Logs ({signals.length})</button>
        <button onClick={() => setTab('costs')} className={`pb-2 text-xs font-semibold uppercase tracking-wider cursor-pointer ${tab === 'costs' ? 'text-primary border-b-2 border-primary' : 'text-muted'}`}>Costs</button>
      </div>

      {tab === 'info' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
            <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-4">Bot Settings</h2>

            <div className="grid grid-cols-3 gap-2 mb-4 pb-4 border-b border-hairline-on-dark">
              <div>
                <label className="block text-xs text-muted mb-1">Name</label>
                <input value={editName} onChange={(e) => setEditName(e.target.value)}
                  className="w-full px-2 py-1.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body focus:outline-none focus:border-primary" />
              </div>
              <div>
                <label className="block text-xs text-muted mb-1">Symbol</label>
                <select value={editSymbol} onChange={(e) => setEditSymbol(e.target.value)}
                  className="w-full px-2 py-1.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body focus:outline-none focus:border-primary">
                  {symbols.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-muted mb-1">Timeframe</label>
                <select value={editTf} onChange={(e) => setEditTf(e.target.value)}
                  className="w-full px-2 py-1.5 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body focus:outline-none focus:border-primary">
                  <option value="M1">M1</option>
                  <option value="M5">M5</option>
                  <option value="M15">M15</option>
                  <option value="H1">H1</option>
                </select>
              </div>
              <div className="col-span-3 flex justify-end">
                <button onClick={saveEdit} className="px-3 py-1 text-xs rounded bg-primary/10 text-primary border border-primary/50 cursor-pointer hover:bg-primary/20">Save Changes</button>
              </div>
            </div>

            <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-4">Strategy Parameters</h2>

            <div className="space-y-4">
              {/* Risk Management */}
              <div>
                <p className="text-xs font-semibold text-body mb-2 border-b border-hairline-on-dark pb-1">Risk Management</p>
                <div className="space-y-3">
                  <div>
                    <label className="flex justify-between text-xs text-muted mb-1">
                      <span>Risk Per Trade</span>
                      <span className="font-mono text-body">{((parsedParams?.risk_percent ?? 0.01) * 100).toFixed(1)}%</span>
                    </label>
                    <input type="range" min="0.1" max="5" step="0.1" value={((parsedParams?.risk_percent ?? 0.01) * 100).toFixed(1)}
                      onChange={(e) => {
                        const p = { ...parsedParams }
                        p.risk_percent = parseFloat(e.target.value) / 100
                        setParamsText(JSON.stringify(p, null, 2))
                      }}
                      className="w-full accent-primary cursor-pointer" />
                  </div>
                  <div>
                    <label className="flex justify-between text-xs text-muted mb-1">
                      <span>Daily Loss Limit</span>
                      <span className="font-mono text-body">{((parsedParams?.daily_loss_limit_percent ?? 0.03) * 100).toFixed(0)}%</span>
                    </label>
                    <input type="range" min="1" max="10" step="1" value={((parsedParams?.daily_loss_limit_percent ?? 0.03) * 100).toFixed(0)}
                      onChange={(e) => {
                        const p = { ...parsedParams }
                        p.daily_loss_limit_percent = parseFloat(e.target.value) / 100
                        setParamsText(JSON.stringify(p, null, 2))
                      }}
                      className="w-full accent-primary cursor-pointer" />
                  </div>
                  <div>
                    <label className="flex justify-between text-xs text-muted mb-1">
                      <span>Max Consecutive Losses</span>
                      <span className="font-mono text-body">{parsedParams?.max_consecutive_losses ?? 3}</span>
                    </label>
                    <input type="range" min="1" max="10" step="1" value={parsedParams?.max_consecutive_losses ?? 3}
                      onChange={(e) => {
                        const p = { ...parsedParams }
                        p.max_consecutive_losses = parseInt(e.target.value)
                        setParamsText(JSON.stringify(p, null, 2))
                      }}
                      className="w-full accent-primary cursor-pointer" />
                  </div>
                  <div>
                    <label className="flex justify-between text-xs text-muted mb-1">
                      <span>Drawdown Alert</span>
                      <span className="font-mono text-body">{parsedParams?.drawdown_alert_percent ?? 10}%</span>
                    </label>
                    <input type="range" min="1" max="50" step="1" value={parsedParams?.drawdown_alert_percent ?? 10}
                      onChange={(e) => {
                        const p = { ...parsedParams }
                        p.drawdown_alert_percent = parseInt(e.target.value)
                        setParamsText(JSON.stringify(p, null, 2))
                      }}
                      className="w-full accent-primary cursor-pointer" />
                  </div>
                </div>
              </div>

              {/* Order Block */}
              <div>
                <p className="text-xs font-semibold text-body mb-2 border-b border-hairline-on-dark pb-1">Order Block</p>
                <div className="space-y-3">
                  <div>
                    <label className="flex justify-between text-xs text-muted mb-1">
                      <span>OB Strong Score</span>
                      <span className="font-mono text-body">{parsedParams?.ob_strong_score ?? 6}</span>
                    </label>
                    <input type="range" min="3" max="10" step="1" value={parsedParams?.ob_strong_score ?? 6}
                      onChange={(e) => {
                        const p = { ...parsedParams }
                        p.ob_strong_score = parseInt(e.target.value)
                        setParamsText(JSON.stringify(p, null, 2))
                      }}
                      className="w-full accent-primary cursor-pointer" />
                  </div>
                  <div>
                    <label className="flex justify-between text-xs text-muted mb-1">
                      <span>TP Multiple (R)</span>
                      <span className="font-mono text-body">{parsedParams?.tp_r_multiple ?? 2.0}x</span>
                    </label>
                    <input type="range" min="1.0" max="5.0" step="0.1" value={parsedParams?.tp_r_multiple ?? 2.0}
                      onChange={(e) => {
                        const p = { ...parsedParams }
                        p.tp_r_multiple = parseFloat(e.target.value)
                        setParamsText(JSON.stringify(p, null, 2))
                      }}
                      className="w-full accent-primary cursor-pointer" />
                  </div>
                  <div>
                    <label className="flex justify-between text-xs text-muted mb-1">
                      <span>SL Buffer Ratio</span>
                      <span className="font-mono text-body">{parsedParams?.sl_buffer_ratio ?? 0.3}</span>
                    </label>
                    <input type="range" min="0" max="1.0" step="0.05" value={parsedParams?.sl_buffer_ratio ?? 0.3}
                      onChange={(e) => {
                        const p = { ...parsedParams }
                        p.sl_buffer_ratio = parseFloat(e.target.value)
                        setParamsText(JSON.stringify(p, null, 2))
                      }}
                      className="w-full accent-primary cursor-pointer" />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">Allow Tested Once</span>
                    <button onClick={() => {
                      const p = { ...parsedParams }
                      p.allow_tested_once = !p.allow_tested_once
                      setParamsText(JSON.stringify(p, null, 2))
                    }} className={`w-10 h-5 rounded-full transition-colors cursor-pointer ${(parsedParams?.allow_tested_once ?? true) ? 'bg-trading-up' : 'bg-surface-400'}`}>
                      <span className={`block w-4 h-4 bg-white rounded-full transition-transform ${(parsedParams?.allow_tested_once ?? true) ? 'translate-x-5' : 'translate-x-0.5'}`} />
                    </button>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">M5 Confirmation Required</span>
                    <button onClick={() => {
                      const p = { ...parsedParams }
                      p.require_m5_confirmation = !p.require_m5_confirmation
                      setParamsText(JSON.stringify(p, null, 2))
                    }} className={`w-10 h-5 rounded-full transition-colors cursor-pointer ${parsedParams?.require_m5_confirmation ? 'bg-trading-up' : 'bg-surface-400'}`}>
                      <span className={`block w-4 h-4 bg-white rounded-full transition-transform ${parsedParams?.require_m5_confirmation ? 'translate-x-5' : 'translate-x-0.5'}`} />
                    </button>
                  </div>
                </div>
              </div>

              {/* Trailing Stop */}
              <div>
                <p className="text-xs font-semibold text-body mb-2 border-b border-hairline-on-dark pb-1">Trailing Stop</p>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">Enabled</span>
                    <button onClick={() => {
                      const p = { ...parsedParams }
                      p.trailing_enabled = !p.trailing_enabled
                      setParamsText(JSON.stringify(p, null, 2))
                    }} className={`w-10 h-5 rounded-full transition-colors cursor-pointer ${parsedParams?.trailing_enabled ? 'bg-trading-up' : 'bg-surface-400'}`}>
                      <span className={`block w-4 h-4 bg-white rounded-full transition-transform ${parsedParams?.trailing_enabled ? 'translate-x-5' : 'translate-x-0.5'}`} />
                    </button>
                  </div>
                  {parsedParams?.trailing_enabled && (
                    <>
                      <div>
                        <label className="flex justify-between text-xs text-muted mb-1">
                          <span>Activation (pips)</span>
                          <span className="font-mono text-body">{parsedParams?.trail_activation_pips ?? 10}</span>
                        </label>
                        <input type="range" min="1" max="50" step="1" value={parsedParams?.trail_activation_pips ?? 10}
                          onChange={(e) => {
                            const p = { ...parsedParams }
                            p.trail_activation_pips = parseInt(e.target.value)
                            setParamsText(JSON.stringify(p, null, 2))
                          }}
                          className="w-full accent-primary cursor-pointer" />
                      </div>
                      <div>
                        <label className="flex justify-between text-xs text-muted mb-1">
                          <span>Distance (pips)</span>
                          <span className="font-mono text-body">{parsedParams?.trail_distance_pips ?? 5}</span>
                        </label>
                        <input type="range" min="1" max="30" step="1" value={parsedParams?.trail_distance_pips ?? 5}
                          onChange={(e) => {
                            const p = { ...parsedParams }
                            p.trail_distance_pips = parseInt(e.target.value)
                            setParamsText(JSON.stringify(p, null, 2))
                          }}
                          className="w-full accent-primary cursor-pointer" />
                      </div>
                      <div>
                        <label className="flex justify-between text-xs text-muted mb-1">
                          <span>Step (pips)</span>
                          <span className="font-mono text-body">{parsedParams?.trail_step_pips ?? 1}</span>
                        </label>
                        <input type="range" min="0.5" max="10" step="0.5" value={parsedParams?.trail_step_pips ?? 1}
                          onChange={(e) => {
                            const p = { ...parsedParams }
                            p.trail_step_pips = parseFloat(e.target.value)
                            setParamsText(JSON.stringify(p, null, 2))
                          }}
                          className="w-full accent-primary cursor-pointer" />
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>

            <button onClick={saveParams} className="mt-4 px-4 py-1.5 text-xs rounded bg-primary/10 text-primary border border-primary/50 cursor-pointer hover:bg-primary/20">Save Params</button>

            <details className="mt-4">
              <summary className="text-xs text-muted cursor-pointer hover:text-body">Advanced (JSON)</summary>
              <textarea value={paramsText} onChange={(e) => setParamsText(e.target.value)}
                className="w-full h-48 bg-canvas-dark border border-surface-400 rounded text-xs font-mono text-body p-3 mt-2 focus:outline-none focus:border-primary resize-none" />
            </details>

            <div className="mt-4 pt-4 border-t border-hairline-on-dark">
              <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Telegram Alert Chat</h2>
              <div className="flex gap-2">
                <input value={alertChatId}
                  onChange={e => setAlertChatId(e.target.value)}
                  placeholder="-100123456789 (leave empty = use global)"
                  className="flex-1 px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body font-mono focus:outline-none focus:border-primary" />
                <button onClick={async () => {
                  try {
                    await client.put(`/bots/${botId}/alert-chat`, { chat_id: alertChatId })
                    addToast('Alert chat saved', 'success')
                  } catch { addToast('Failed to save', 'error') }
                }} className="px-3 py-1.5 text-xs bg-primary/10 text-primary border border-primary/50 rounded cursor-pointer">
                  Save
                </button>
              </div>
              <p className="text-xs text-muted mt-1">Set a custom Telegram chat for this bot. Leave empty to use the global chat from Settings.</p>
            </div>
          </div>
          <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
            <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Stats</h2>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between"><span className="text-muted">Total Realized PnL</span><span className={`font-mono ${(wallet?.realized_pnl ?? 0) >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>${wallet?.realized_pnl?.toFixed(2) ?? '—'}</span></div>
              <div className="flex justify-between"><span className="text-muted">Total Trades</span><span className="font-mono">{botStats.closed_trades}</span></div>
              <div className="flex justify-between"><span className="text-muted">Wins / Losses</span><span className="font-mono">{botStats.wins} / {botStats.losses}</span></div>
              <div className="flex justify-between"><span className="text-muted">Net PnL</span><span className={`font-mono ${botStats.net_pnl >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>${botStats.net_pnl.toFixed(2)}</span></div>
              <div className="flex justify-between"><span className="text-muted">Max Drawdown</span><span className="font-mono text-rose-500">${botStats.max_drawdown_usd.toFixed(2)}</span></div>
            </div>
          </div>
        </div>
      )}



      {tab === 'signals' && (
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg overflow-hidden">
          {signals.length > 0 ? (
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-hairline-on-dark text-muted">
                  <th className="text-left p-3">Time</th>
                  <th className="text-left p-3">Event</th>
                  <th className="text-left p-3">Message</th>
                </tr>
              </thead>
              <tbody>
                {signals.map((s) => (
                  <tr key={s.id} className="border-b border-surface-elevated-dark">
                    <td className="p-3 font-mono whitespace-nowrap">{new Date(s.created_at * 1000).toLocaleString()}</td>
                    <td className="p-3"><span className="px-2 py-0.5 rounded bg-surface-elevated-dark text-muted">{s.event_type}</span></td>
                    <td className="p-3 max-w-md truncate">{s.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-6 text-center text-muted text-xs">No signal logs for this bot.</div>
          )}
        </div>
      )}

      {tab === 'costs' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
              <p className="text-xs text-muted mb-1">Total Commission</p>
              <p className="font-mono text-lg font-semibold text-trading-down">${(costs?.total_commission ?? 0).toFixed(2)}</p>
            </div>
            <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
              <p className="text-xs text-muted mb-1">Total Spread Cost</p>
              <p className="font-mono text-lg font-semibold text-trading-down">${(costs?.total_spread_cost ?? 0).toFixed(2)}</p>
            </div>
            <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
              <p className="text-xs text-muted mb-1">Total Slippage</p>
              <p className="font-mono text-lg font-semibold text-trading-down">${(costs?.total_slippage ?? 0).toFixed(2)}</p>
            </div>
            <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
              <p className="text-xs text-muted mb-1">Total Costs</p>
              <p className="font-mono text-lg font-semibold text-trading-down">${(costs?.total_costs ?? 0).toFixed(2)}</p>
            </div>
          </div>
          {costs?.trades_with_costs && costs.trades_with_costs.length > 0 && (
            <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-hairline-on-dark text-muted">
                    <th className="text-left p-3">#</th>
                    <th className="text-right p-3">Gross PnL</th>
                    <th className="text-right p-3">Commission</th>
                    <th className="text-right p-3">Slippage</th>
                    <th className="text-right p-3">Spread</th>
                    <th className="text-right p-3">Net PnL</th>
                  </tr>
                </thead>
                <tbody>
                  {costs.trades_with_costs.map((tc, i) => (
                    <tr key={i} className="border-b border-surface-elevated-dark">
                      <td className="p-3 font-mono">{i + 1}</td>
                      <td className={`p-3 font-mono text-right ${tc.pnl_gross >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>{tc.pnl_gross >= 0 ? '+' : ''}${tc.pnl_gross.toFixed(2)}</td>
                      <td className="p-3 font-mono text-right text-trading-down">{(tc.commission || 0) > 0 ? `-$${tc.commission.toFixed(2)}` : '$0.00'}</td>
                      <td className="p-3 font-mono text-right text-trading-down">{tc.slippage ? `-$${Math.abs(tc.slippage).toFixed(2)}` : '$0.00'}</td>
                      <td className="p-3 font-mono text-right text-trading-down">{(tc.spread_cost || 0) > 0 ? `-$${tc.spread_cost.toFixed(2)}` : '$0.00'}</td>
                      <td className={`p-3 font-mono text-right ${tc.pnl_net >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>{tc.pnl_net >= 0 ? '+' : ''}${tc.pnl_net.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {trades.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Trade History</h2>
          <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline-on-dark text-muted text-xs">
                  <th className="text-left p-3">Side</th>
                  <th className="text-right p-3">Entry</th>
                  <th className="text-right p-3">Exit</th>
                  <th className="text-right p-3">PnL</th>
                  <th className="text-right p-3">R</th>
                  <th className="text-left p-3">Exit Reason</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => (
                  <tr key={t.id} className="border-b border-surface-elevated-dark">
                    <td className={`p-3 font-mono text-xs font-semibold ${t.side === 'buy' ? 'text-trading-up' : 'text-trading-down'}`}>{t.side.toUpperCase()}</td>
                    <td className="p-3 font-mono text-xs text-right">{t.entry.toFixed(2)}</td>
                    <td className="p-3 font-mono text-xs text-right">{t.exit?.toFixed(2) ?? '—'}</td>
                    <td className={`p-3 font-mono text-xs text-right ${t.pnl != null ? (t.pnl >= 0 ? 'text-trading-up' : 'text-trading-down') : ''}`}>{t.pnl != null ? `${t.pnl >= 0 ? '+' : ''}$${t.pnl.toFixed(2)}` : '—'}</td>
                    <td className={`p-3 font-mono text-xs text-right ${t.r_multiple != null ? (t.r_multiple >= 0 ? 'text-trading-up' : 'text-trading-down') : ''}`}>{t.r_multiple?.toFixed(2) ?? '—'}</td>
                    <td className="p-3 text-xs text-muted">{t.exit_reason ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {showCloneModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-6 max-w-sm w-full mx-4">
            <h3 className="text-sm font-semibold text-body mb-4">Clone Bot</h3>
            <label className="block text-xs text-muted mb-1">New bot name</label>
            <input value={cloneName} onChange={(e) => setCloneName(e.target.value)}
              className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body mb-4 focus:outline-none focus:border-primary" />
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowCloneModal(false)}
                className="px-3 py-1.5 text-xs rounded bg-surface-elevated-dark text-muted border border-hairline-on-dark cursor-pointer">Cancel</button>
              <button onClick={doClone}
                className="px-3 py-1.5 text-xs rounded bg-primary/10 text-primary border border-primary/50 cursor-pointer">Clone</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
