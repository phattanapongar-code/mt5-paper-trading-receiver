import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import client from '../api/client'
import type { BotState, Wallet, Trade, BotSignalLog } from '../types/api'

type Tab = 'info' | 'signals'

export default function BotDetail() {
  const { botId } = useParams()
  const navigate = useNavigate()
  const [state, setState] = useState<BotState | null>(null)
  const [wallet, setWallet] = useState<Wallet | null>(null)
  const [trades, setTrades] = useState<Trade[]>([])
  const [signals, setSignals] = useState<BotSignalLog[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<Tab>('info')
  const [paramsText, setParamsText] = useState('')

  const fetchData = useCallback(async () => {
    try {
      const [stateRes, walletRes, tradesRes, signalsRes] = await Promise.all([
        client.get<BotState>(`/bots/${botId}/state`),
        client.get<Wallet>(`/bots/${botId}/wallet`),
        client.get<Trade[]>(`/bots/${botId}/trades`, { params: { limit: 20 } }),
        client.get<BotSignalLog[]>(`/signal-logs?bot_id=${botId}&limit=50`),
      ])
      setState(stateRes.data)
      setWallet(walletRes.data)
      setTrades(tradesRes.data)
      setSignals(signalsRes.data)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [botId])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 3000)
    return () => clearInterval(interval)
  }, [fetchData])

  useEffect(() => {
    if (state?.bot?.parameters) {
      setParamsText(JSON.stringify(state.bot.parameters, null, 2))
    }
  }, [state?.bot?.parameters])

  const toggleBot = useCallback(async (enabled: boolean) => {
    await client.post(`/bots/${botId}/${enabled ? 'disable' : 'enable'}`)
    fetchData()
  }, [botId, fetchData])

  const resetWallet = useCallback(async () => {
    const balance = prompt('New balance:')
    if (balance) {
      await client.post(`/bots/${botId}/wallet/reset`, { balance: parseFloat(balance) })
      fetchData()
    }
  }, [botId, fetchData])

  const cloneBot = useCallback(async () => {
    const name = prompt('New bot name:', (state?.bot?.name ?? '') + ' (clone)')
    if (!name || !state) return
    await client.post('/bots', {
      profile_id: state.bot.profile_id,
      name,
      strategy_type: state.bot.strategy_type,
      strategy_version: state.bot.strategy_version,
      symbol: state.bot.symbol,
      timeframe: state.bot.timeframe,
      enabled: false,
      initial_balance: wallet?.initial_balance ?? 500,
      parameters: state.bot.parameters,
    })
    alert('Bot cloned!')
    navigate('/bots')
  }, [state, wallet, navigate])

  const saveParams = useCallback(async () => {
    try {
      const parsed = JSON.parse(paramsText)
      await client.put(`/bots/${botId}`, { parameters: parsed })
      alert('Parameters saved!')
    } catch {
      alert('Invalid JSON')
    }
  }, [botId, paramsText])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-text-muted text-sm font-mono">Loading...</div>
      </div>
    )
  }

  if (!state) {
    return (
      <div className="p-6">
        <button onClick={() => navigate('/bots')} className="text-cyber-cyan text-sm mb-4 cursor-pointer">&larr; Back</button>
        <p className="text-text-muted text-sm">Bot not found</p>
      </div>
    )
  }

  const bot = state.bot

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/bots')} className="text-text-muted hover:text-text-primary text-sm cursor-pointer">&larr;</button>
          <h1 className="text-lg font-semibold text-text-primary">{bot.name}</h1>
          <span className="text-xs font-mono text-text-muted">{bot.strategy_type} v{bot.strategy_version}</span>
          <span className="text-xs font-mono text-text-muted">{bot.symbol} {bot.timeframe}</span>
        </div>
        <div className="flex gap-2">
          <button onClick={cloneBot} className="px-3 py-1.5 text-xs rounded-md bg-surface-700 text-text-secondary hover:text-text-primary border border-surface-500 cursor-pointer">Clone</button>
          <button onClick={() => toggleBot(!bot.enabled)}
            className={`px-3 py-1.5 text-xs rounded-md font-semibold transition-colors cursor-pointer ${
              bot.enabled
                ? 'bg-cyber-green/20 text-cyber-green border border-cyber-green/50'
                : 'bg-surface-600 text-text-muted border border-surface-400'
            }`}>
            {bot.enabled ? 'ENABLED' : 'DISABLED'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-surface-800 border border-surface-500 rounded-lg p-4">
          <p className="text-xs text-text-muted mb-1">Wallet Balance</p>
          <p className="font-mono text-xl font-semibold text-cyber-cyan">
            ${wallet?.balance.toFixed(2) ?? '—'}
          </p>
          <p className="text-xs text-text-muted mt-1">
            Initial: ${wallet?.initial_balance.toFixed(2) ?? '—'}
          </p>
        </div>
        <div className="bg-surface-800 border border-surface-500 rounded-lg p-4">
          <p className="text-xs text-text-muted mb-1">Realized PnL</p>
          <p className={`font-mono text-xl font-semibold ${(wallet?.realized_pnl ?? 0) >= 0 ? 'text-cyber-green' : 'text-cyber-red'}`}>
            {(wallet?.realized_pnl ?? 0) >= 0 ? '+' : ''}${wallet?.realized_pnl.toFixed(2) ?? '—'}
          </p>
        </div>
        <div className="bg-surface-800 border border-surface-500 rounded-lg p-4">
          <p className="text-xs text-text-muted mb-1">Runtime</p>
          <div className="space-y-1">
            <p className="text-xs font-mono">
              <span className="text-text-muted">Trend: </span>
              <span className={state.runtime?.latest_trend === 'BULLISH' ? 'text-cyber-green' : state.runtime?.latest_trend === 'BEARISH' ? 'text-cyber-red' : 'text-text-muted'}>
                {state.runtime?.latest_trend ?? '—'}
              </span>
            </p>
            <p className="text-xs font-mono">
              <span className="text-text-muted">Consecutive Losses: </span>
              <span className={state.runtime && state.runtime.consecutive_losses > 0 ? 'text-cyber-red' : 'text-cyber-green'}>
                {state.runtime?.consecutive_losses ?? '—'}
              </span>
            </p>
            <p className="text-xs font-mono">
              <span className="text-text-muted">Daily PnL: </span>
              <span className={(state.runtime?.daily_realized_pnl ?? 0) >= 0 ? 'text-cyber-green' : 'text-cyber-red'}>
                ${state.runtime?.daily_realized_pnl.toFixed(2) ?? '—'}
              </span>
            </p>
          </div>
        </div>
      </div>

      <div className="flex gap-2">
        <button onClick={resetWallet} className="px-3 py-1.5 text-xs rounded-md bg-surface-700 text-text-secondary hover:text-text-primary border border-surface-500 transition-colors cursor-pointer">Reset Wallet</button>
      </div>

      {state.position && (
        <div className="bg-surface-800 border border-surface-500 rounded-lg p-4">
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Open Position</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
            <div><span className="text-text-muted text-xs">Side</span>
              <p className={`font-mono font-semibold ${state.position.side === 'buy' ? 'text-cyber-green' : 'text-cyber-red'}`}>{state.position.side.toUpperCase()}</p></div>
            <div><span className="text-text-muted text-xs">Lot</span><p className="font-mono">{state.position.lot}</p></div>
            <div><span className="text-text-muted text-xs">Entry</span><p className="font-mono">{state.position.entry.toFixed(2)}</p></div>
            <div><span className="text-text-muted text-xs">SL</span><p className="font-mono">{state.position.stop_loss?.toFixed(2) ?? '—'}</p></div>
            <div><span className="text-text-muted text-xs">TP</span><p className="font-mono">{state.position.take_profit?.toFixed(2) ?? '—'}</p></div>
          </div>
        </div>
      )}

      {state.pending && (
        <div className="bg-surface-800 border border-cyber-cyan/30 rounded-lg p-4">
          <h2 className="text-xs font-semibold text-cyber-cyan uppercase tracking-wider mb-3">Pending Order</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div><span className="text-text-muted text-xs">Side</span>
              <p className={`font-mono text-sm font-semibold ${state.pending.side === 'buy' ? 'text-cyber-green' : 'text-cyber-red'}`}>{state.pending.side.toUpperCase()}</p></div>
            <div><span className="text-text-muted text-xs">Entry</span><p className="font-mono text-sm">{state.pending.entry.toFixed(2)}</p></div>
            <div><span className="text-text-muted text-xs">SL</span><p className="font-mono text-sm">{state.pending.stop_loss.toFixed(2)}</p></div>
            <div><span className="text-text-muted text-xs">TP</span><p className="font-mono text-sm">{state.pending.take_profit.toFixed(2)}</p></div>
            <div><span className="text-text-muted text-xs">RR</span><p className="font-mono text-sm text-cyber-yellow">{state.pending.risk_reward.toFixed(2)}</p></div>
          </div>
        </div>
      )}

      <div className="flex gap-4 border-b border-surface-500">
        <button onClick={() => setTab('info')} className={`pb-2 text-xs font-semibold uppercase tracking-wider cursor-pointer ${tab === 'info' ? 'text-cyber-cyan border-b-2 border-cyber-cyan' : 'text-text-muted'}`}>Info / Params</button>
        <button onClick={() => setTab('signals')} className={`pb-2 text-xs font-semibold uppercase tracking-wider cursor-pointer ${tab === 'signals' ? 'text-cyber-cyan border-b-2 border-cyber-cyan' : 'text-text-muted'}`}>Signal Logs ({signals.length})</button>
      </div>

      {tab === 'info' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-surface-800 border border-surface-500 rounded-lg p-4">
            <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Bot Parameters</h2>
            <textarea value={paramsText} onChange={(e) => setParamsText(e.target.value)}
              className="w-full h-64 bg-surface-900 border border-surface-400 rounded text-xs font-mono text-text-primary p-3 focus:outline-none focus:border-cyber-cyan resize-none" />
            <button onClick={saveParams} className="mt-2 px-3 py-1.5 text-xs bg-cyber-cyan/20 text-cyber-cyan border border-cyber-cyan/50 rounded cursor-pointer">Save Params</button>
          </div>
          <div className="bg-surface-800 border border-surface-500 rounded-lg p-4">
            <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Stats</h2>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between"><span className="text-text-muted">Total Realized PnL</span><span className={`font-mono ${(wallet?.realized_pnl ?? 0) >= 0 ? 'text-cyber-green' : 'text-cyber-red'}`}>${wallet?.realized_pnl?.toFixed(2) ?? '—'}</span></div>
              <div className="flex justify-between"><span className="text-text-muted">Total Trades</span><span className="font-mono">{state.stats?.closed_trades ?? '—'}</span></div>
              <div className="flex justify-between"><span className="text-text-muted">Wins / Losses</span><span className="font-mono">{state.stats?.wins ?? '—'} / {state.stats?.losses ?? '—'}</span></div>
              <div className="flex justify-between"><span className="text-text-muted">Net PnL</span><span className={`font-mono ${(state.stats?.net_pnl ?? 0) >= 0 ? 'text-cyber-green' : 'text-cyber-red'}`}>${state.stats?.net_pnl?.toFixed(2) ?? '—'}</span></div>
              <div className="flex justify-between"><span className="text-text-muted">Max Drawdown</span><span className="font-mono text-rose-500">${state.stats?.max_drawdown_usd?.toFixed(2) ?? '—'}</span></div>
            </div>
          </div>
        </div>
      )}

      {tab === 'signals' && (
        <div className="bg-surface-800 border border-surface-500 rounded-lg overflow-hidden">
          {signals.length > 0 ? (
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-surface-500 text-text-muted">
                  <th className="text-left p-3">Time</th>
                  <th className="text-left p-3">Event</th>
                  <th className="text-left p-3">Message</th>
                </tr>
              </thead>
              <tbody>
                {signals.map((s) => (
                  <tr key={s.id} className="border-b border-surface-600">
                    <td className="p-3 font-mono whitespace-nowrap">{new Date(s.created_at * 1000).toLocaleString()}</td>
                    <td className="p-3"><span className="px-2 py-0.5 rounded bg-surface-700 text-text-muted">{s.event_type}</span></td>
                    <td className="p-3 max-w-md truncate">{s.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-6 text-center text-text-muted text-xs">No signal logs for this bot.</div>
          )}
        </div>
      )}

      {trades.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Trade History</h2>
          <div className="bg-surface-800 border border-surface-500 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-500 text-text-muted text-xs">
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
                  <tr key={t.id} className="border-b border-surface-600">
                    <td className={`p-3 font-mono text-xs font-semibold ${t.side === 'buy' ? 'text-cyber-green' : 'text-cyber-red'}`}>{t.side.toUpperCase()}</td>
                    <td className="p-3 font-mono text-xs text-right">{t.entry.toFixed(2)}</td>
                    <td className="p-3 font-mono text-xs text-right">{t.exit?.toFixed(2) ?? '—'}</td>
                    <td className={`p-3 font-mono text-xs text-right ${t.pnl != null ? (t.pnl >= 0 ? 'text-cyber-green' : 'text-cyber-red') : ''}`}>{t.pnl != null ? `${t.pnl >= 0 ? '+' : ''}$${t.pnl.toFixed(2)}` : '—'}</td>
                    <td className={`p-3 font-mono text-xs text-right ${t.r_multiple != null ? (t.r_multiple >= 0 ? 'text-cyber-green' : 'text-cyber-red') : ''}`}>{t.r_multiple?.toFixed(2) ?? '—'}</td>
                    <td className="p-3 text-xs text-text-muted">{t.exit_reason ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
