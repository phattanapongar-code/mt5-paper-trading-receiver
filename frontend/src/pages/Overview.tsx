import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import client from '../api/client'
import { useWebSocket } from '../api/ws'
import { useBotContext } from '../context/BotContext'
import LoadingSpinner from '../components/LoadingSpinner'
import type { Trade, CompareBot, BotState, Wallet } from '../types/api'
import { useMarketStore } from '../stores/useMarketStore'

interface HealthWithTick {
  ok: boolean; sender_online: boolean; websocket_clients: number
  last_seq: number | null; seconds_since_last_message: number | null
  latest_tick: { bid: number; ask: number; spread: number; seq: number } | null
}
import EquityChart from '../components/EquityChart'

export default function Overview() {
  const { selectedBot, allBots, symbol } = useBotContext()
  const [health, setHealth] = useState<HealthWithTick | null>(null)
  const [trades, setTrades] = useState<Trade[]>([])
  const [candles, setCandles] = useState<Record<string, any>[]>([])
  const [compare, setCompare] = useState<CompareBot[]>([])
  const [botState, setBotState] = useState<BotState | null>(null)
  const [wallet, setWallet] = useState<Wallet | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const navigate = useNavigate()

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const storeTick = useMarketStore((state) => state.ticks[(selectedBot?.symbol || symbol).toUpperCase()])

  const fetchData = useCallback(async () => {
    setRefreshing(true)
    try {
      const [healthRes, tradesRes, compareRes, candlesRes] = await Promise.all([
        fetch('/health').then((r) => r.json() as Promise<HealthWithTick>),
        client.get<Trade[]>('/trades', { params: { limit: 12, symbol: selectedBot?.symbol || symbol } }),
        client.get<CompareBot[]>('/compare'),
        client.get<Record<string, any>[]>('/candles/M1', { params: { limit: 1, symbol: selectedBot?.symbol || symbol } }),
      ])
      setHealth(healthRes)
      setTrades(tradesRes.data)
      setCompare(compareRes.data)
      setCandles(candlesRes.data)

      if (selectedBot) {
        const [bs, w] = await Promise.all([
          client.get<BotState>(`/bots/${selectedBot.id}/state`),
          client.get<Wallet>(`/bots/${selectedBot.id}/wallet`),
        ])
        setBotState(bs.data)
        setWallet(w.data)
      } else {
        setBotState(null)
        setWallet(null)
      }
    } catch {
      // ignore
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [selectedBot, allBots, symbol])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [fetchData])

  useWebSocket('/ws/ticks', (msg: any) => {
    if (msg?.tick) {
      setHealth((prev) => prev ? {
        ...prev,
        latest_tick: msg.tick,
        seconds_since_last_message: 0,
        sender_online: true,
      } : prev)
    }
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(fetchData, 5000)
  })

  if (loading && !health) {
    return (
      <div className="flex items-center justify-center h-full bg-canvas-dark">
        <div className="animate-pulse text-muted text-sm font-mono">Loading...</div>
      </div>
    )
  }

  const isBotLive = botState?.runtime?.updated_at != null && (Date.now() / 1000 - botState.runtime.updated_at < 10)
  const tick = storeTick || health?.latest_tick
  const currentCandle = candles[0]
  const currentPrice = tick || (currentCandle ? { bid: currentCandle.close, ask: currentCandle.close, spread: 0, seq: 0 } : null)
  const enabledBots = allBots.filter((b) => b.enabled)

  // Fleet aggregates
  const fleetBalance = compare.reduce((s, b) => s + b.balance, 0)
  const fleetPnl = compare.reduce((s, b) => s + (b.net_pnl ?? 0), 0)
  const fleetTrades = compare.reduce((s, b) => s + (b.closed_trades ?? 0), 0)
  const fleetWins = compare.reduce((s, b) => s + (b.wins ?? 0), 0)
  const fleetWinRate = fleetTrades > 0 ? ((fleetWins / fleetTrades) * 100).toFixed(1) : '—'

  // All open positions across bots
  const openPositions = compare.filter((b) => b.open_positions > 0)

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-body flex items-center gap-2">
          Overview{selectedBot ? ` — ${selectedBot.name}` : ''}
          {refreshing && <LoadingSpinner size={14} />}
          {selectedBot && isBotLive && (
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-trading-up">
              <span className="w-1.5 h-1.5 rounded-full bg-trading-up shadow-[0_0_4px_#0ecb81] animate-pulse" />
              LIVE
            </span>
          )}
          {selectedBot && !isBotLive && botState && (
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-muted">
              <span className="w-1.5 h-1.5 rounded-full bg-surface-400" />
              IDLE
            </span>
          )}
        </h1>
        <div className="flex items-center gap-3 text-xs font-mono">
          <span className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${health?.sender_online ? 'bg-trading-up shadow-[0_0_6px_#0ecb81]' : 'bg-trading-down shadow-[0_0_6px_#f6465d]'}`} />
            {health?.sender_online ? 'ONLINE' : 'OFFLINE'}
          </span>
          <span className="text-muted">
            WS: {health?.websocket_clients ?? 0}
          </span>
        </div>
      </div>

      {/* Market cards — always shown */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <PriceCard label="Bid" value={currentPrice?.bid?.toFixed(2) ?? '—'} numericValue={currentPrice?.bid} accent="primary" />
        <PriceCard label="Ask" value={currentPrice?.ask?.toFixed(2) ?? '—'} numericValue={currentPrice?.ask} accent="primary" />
        <PriceCard label="Spread" value={currentPrice?.spread?.toFixed(1) ?? '—'} numericValue={currentPrice?.spread} accent="primary" />
        <PriceCard label="Last Seq" value={String(currentPrice?.seq ?? '—')} accent="muted" />
      </div>

      {/* Selected Bot: wallet cards */}
      {selectedBot && wallet ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card label={`${selectedBot.name} Balance`} value={`$${wallet.balance.toFixed(2)}`} accent="trading-up" />
          <Card label={`${selectedBot.name} Realized PnL`} value={`${wallet.realized_pnl >= 0 ? '+' : ''}$${wallet.realized_pnl.toFixed(2)}`} accent={wallet.realized_pnl >= 0 ? 'trading-up' : 'trading-down'} />
          <Card label="Trend" value={botState?.runtime?.latest_trend ?? '—'} accent={botState?.runtime?.latest_trend === 'BULLISH' ? 'trading-up' : botState?.runtime?.latest_trend === 'BEARISH' ? 'trading-down' : 'muted'} />
        </div>
      ) : (
        /* All Bots: fleet stats */
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card label="Total Balance" value={`$${fleetBalance.toFixed(2)}`} accent="trading-up" />
          <Card label="Fleet PnL" value={`${fleetPnl >= 0 ? '+' : ''}$${fleetPnl.toFixed(2)}`} accent={fleetPnl >= 0 ? 'trading-up' : 'trading-down'} />
          <Card label="Active Bots" value={`${enabledBots.length} / ${allBots.length}`} accent="primary" />
          <Card label="Win Rate" value={fleetWinRate !== '—' ? `${fleetWinRate}%` : '—'} accent={parseFloat(fleetWinRate) >= 50 ? 'trading-up' : 'trading-down'} />
        </div>
      )}

      {/* Equity chart — fleet (All) or per-bot (selected) */}
      <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
        <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">
          {selectedBot ? `${selectedBot.name} Equity` : 'Fleet Equity'}
        </h2>
        <EquityChart botId={selectedBot?.id} />
      </div>

      {/* Open positions */}
      {selectedBot && botState?.position ? (
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Open Position — {selectedBot.name}</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
            <div>
              <span className="text-muted text-xs">Side</span>
              <p className={`font-mono font-semibold ${botState.position.side === 'buy' ? 'text-trading-up' : 'text-trading-down'}`}>
                {botState.position.side.toUpperCase()}
              </p>
            </div>
            <div>
              <span className="text-muted text-xs">Lot</span>
              <p className="font-mono">{botState.position.lot}</p>
            </div>
            <div>
              <span className="text-muted text-xs">Entry</span>
              <p className="font-mono">{botState.position.entry.toFixed(2)}</p>
            </div>
            <div>
              <span className="text-muted text-xs">SL / TP</span>
              <p className="font-mono text-xs">
                {botState.position.stop_loss?.toFixed(2) ?? '—'} / {botState.position.take_profit?.toFixed(2) ?? '—'}
              </p>
            </div>
            <div>
              <span className="text-muted text-xs">PnL</span>
              <p className={`font-mono ${(botState.position.pnl ?? 0) >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>
                {(botState.position.pnl ?? 0) >= 0 ? '+' : ''}${(botState.position.pnl ?? 0).toFixed(2)}
              </p>
            </div>
          </div>
        </div>
      ) : openPositions.length > 0 ? (
        /* All Bots: list all bots with open positions */
        <div>
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Open Positions</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {openPositions.map((b) => (
              <div key={b.bot_id}
                className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4 hover:bg-surface-elevated-dark/30 cursor-pointer transition-colors"
                onClick={() => navigate(`/bots/${b.bot_id}`)}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-body">{b.name}</span>
                  <span className="text-xs text-muted">{b.symbol}</span>
                </div>
                <p className="text-xs text-muted">Has open position</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Bot Fleet grid (All Bots) */}
      {!selectedBot && compare.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Bot Fleet</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {compare.map((b) => (
              <div key={b.bot_id}
                className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4 hover:bg-surface-elevated-dark/30 cursor-pointer transition-colors"
                onClick={() => navigate(`/bots/${b.bot_id}`)}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-body">{b.name}</span>
                  <span className={`text-xs font-mono ${(b.net_pnl ?? 0) >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>
                    {(b.net_pnl ?? 0) >= 0 ? '+' : ''}${(b.net_pnl ?? 0).toFixed(2)}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted">
                  <span>{b.symbol} {b.timeframe}</span>
                  <span>{b.closed_trades} trades</span>
                  <span>{b.win_rate != null ? `${b.win_rate.toFixed(0)}%` : '—'}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Trades */}
      {trades.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Recent Trades</h2>
          <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline-on-dark text-muted text-xs">
                  <th className="text-left p-3 font-medium">ID</th>
                  <th className="text-left p-3 font-medium">Side</th>
                  <th className="text-left p-3 font-medium">Lot</th>
                  <th className="text-right p-3 font-medium">Entry</th>
                  <th className="text-right p-3 font-medium">Exit</th>
                  <th className="text-right p-3 font-medium">PnL</th>
                  <th className="text-right p-3 font-medium">R</th>
                  <th className="text-left p-3 font-medium">Reason</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => (
                  <tr key={t.id} className="border-b border-surface-elevated-dark hover:bg-surface-card-dark/50">
                    <td className="p-3 font-mono text-xs">{t.id}</td>
                    <td className="p-3">
                      <span className={`text-xs font-semibold ${t.side === 'buy' ? 'text-trading-up' : 'text-trading-down'}`}>
                        {t.side.toUpperCase()}
                      </span>
                    </td>
                    <td className="p-3 font-mono text-xs">{t.lot}</td>
                    <td className="p-3 font-mono text-xs text-right">{t.entry.toFixed(2)}</td>
                    <td className="p-3 font-mono text-xs text-right">{t.exit?.toFixed(2) ?? '—'}</td>
                    <td className={`p-3 font-mono text-xs text-right ${t.pnl != null ? (t.pnl >= 0 ? 'text-trading-up' : 'text-trading-down') : ''}`}>
                      {t.pnl != null ? `${t.pnl >= 0 ? '+' : ''}$${t.pnl.toFixed(2)}` : '—'}
                    </td>
                    <td className={`p-3 font-mono text-xs text-right ${t.r_multiple != null ? (t.r_multiple >= 0 ? 'text-trading-up' : 'text-trading-down') : ''}`}>
                      {t.r_multiple != null ? t.r_multiple.toFixed(2) : '—'}
                    </td>
                    <td className="p-3 text-xs text-muted">{t.exit_reason ?? '—'}</td>
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

function Card({ label, value, accent }: { label: string; value: string; accent: 'primary' | 'trading-up' | 'trading-down' | 'muted' }) {
  const accentMap = {
    primary: 'border-primary/30 text-primary',
    'trading-up': 'border-trading-up/30 text-trading-up',
    'trading-down': 'border-trading-down/30 text-trading-down',
    muted: 'border-hairline-on-dark text-muted',
  }
  return (
    <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
      <p className="text-xs text-muted mb-1">{label}</p>
      <p className={`font-mono text-lg font-semibold ${accentMap[accent]}`}>{value}</p>
    </div>
  )
}

function PriceCard({ label, value, numericValue, accent }: { 
  label: string; 
  value: string; 
  numericValue?: number;
  accent: 'primary' | 'trading-up' | 'trading-down' | 'muted' 
}) {
  const [flashClass, setFlashClass] = useState('')
  const prevValueRef = useRef<number | null>(null)

  useEffect(() => {
    if (numericValue === undefined || numericValue === null) return
    const prev = prevValueRef.current
    if (prev !== null && prev !== numericValue) {
      if (numericValue > prev) {
        setFlashClass('animate-flash-up')
      } else if (numericValue < prev) {
        setFlashClass('animate-flash-down')
      }
      const timer = setTimeout(() => setFlashClass(''), 500)
      prevValueRef.current = numericValue
      return () => clearTimeout(timer)
    }
    prevValueRef.current = numericValue
  }, [numericValue])

  const accentMap = {
    primary: 'border-primary/30 text-primary',
    'trading-up': 'border-trading-up/30 text-trading-up',
    'trading-down': 'border-trading-down/30 text-trading-down',
    muted: 'border-hairline-on-dark text-muted',
  }

  return (
    <div className={`bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4 transition-all duration-300 ${flashClass}`}>
      <p className="text-xs text-muted mb-1">{label}</p>
      <p className={`font-mono text-lg font-semibold ${accentMap[accent]}`}>{value}</p>
    </div>
  )
}
