import { useState, useEffect, useCallback } from 'react'
import client from '../api/client'
import { useBotContext } from '../context/BotContext'
import LoadingSpinner from '../components/LoadingSpinner'
import type { PendingOrder } from '../types/api'

function ExpiryCountdown({ expiresAt }: { expiresAt: number }) {
  const [remaining, setRemaining] = useState('')
  useEffect(() => {
    const update = () => {
      const diff = expiresAt * 1000 - Date.now()
      if (diff <= 0) { setRemaining('EXPIRED'); return }
      const mins = Math.floor(diff / 60000)
      const secs = Math.floor((diff % 60000) / 1000)
      setRemaining(`${mins}m ${secs}s`)
    }
    update()
    const interval = setInterval(update, 1000)
    return () => clearInterval(interval)
  }, [expiresAt])
  return <span className={`text-xs font-mono ${remaining === 'EXPIRED' ? 'text-trading-down' : 'text-muted'}`}>{remaining}</span>
}

interface PendingOrderWithBot extends PendingOrder {
  bot_name?: string
  bot_id?: number
}

export default function PendingOrders() {
  const { selectedBot } = useBotContext()
  const [orders, setOrders] = useState<PendingOrderWithBot[]>([])
  const [rejections, setRejections] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchData = useCallback(async () => {
    setRefreshing(true)
    try {
      const botParam = selectedBot ? `&bot_id=${selectedBot.id}` : ''
      const [ordersRes, rejRes] = await Promise.all([
        client.get<PendingOrderWithBot[]>(`/pending-orders?limit=50${botParam}`),
        client.get<any[]>(`/pending-orders/rejections?limit=20${botParam}`),
      ])
      setOrders(ordersRes.data)
      setRejections(rejRes.data)
    } catch {
      // ignore
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [selectedBot])

  const cancelOrder = useCallback(async (orderId: number) => {
    try {
      const params = selectedBot ? `?bot_id=${selectedBot.id}` : ''
      await client.post(`/pending-orders/${orderId}/cancel${params}`)
      fetchData()
    } catch {
      // ignore
    }
  }, [selectedBot, fetchData])

  const evaluateAll = useCallback(async () => {
    await client.post('/pending-orders/evaluate')
    fetchData()
  }, [fetchData])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [fetchData])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-muted text-sm font-mono">Loading...</div>
      </div>
    )
  }

  const activeOrders = orders.filter((o) => o.status === 'pending')
  const pastOrders = orders.filter((o) => o.status !== 'pending')

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-body">
          Pending Orders{selectedBot ? ` — ${selectedBot.name}` : ''}
          {refreshing && <LoadingSpinner size={14} />}
        </h1>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted font-mono">{orders.length} total · {activeOrders.length} active</span>
          <button
            onClick={evaluateAll}
            className="px-3 py-1.5 text-xs rounded-md bg-primary/10 text-primary border border-primary/50 hover:bg-primary/20 transition-colors cursor-pointer"
          >
            Re-evaluate
          </button>
        </div>
      </div>

      {/* Active pending orders */}
      {activeOrders.length > 0 ? (
        <div className="space-y-3">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">Active Pending Orders</h2>
          {activeOrders.map((order) => (
            <div key={order.id} className="bg-surface-card-dark border border-primary/30 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <p className="text-xs font-semibold text-primary uppercase tracking-wider">#{order.id}</p>
                  {order.bot_name && (
                    <span className="text-xs text-muted font-mono">{order.bot_name}</span>
                  )}
                  {order.bot_id && !order.bot_name && (
                    <span className="text-xs text-muted font-mono">bot #{order.bot_id}</span>
                  )}
                  {order.expires_at && <ExpiryCountdown expiresAt={order.expires_at} />}
                </div>
                <button
                  onClick={() => cancelOrder(order.id)}
                  className="px-2.5 py-1 text-xs rounded bg-trading-down/10 text-trading-down border border-trading-down/50 hover:bg-trading-down/20 transition-colors cursor-pointer"
                >
                  Cancel
                </button>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <div>
                  <p className="text-xs text-muted">Side</p>
                  <p className={`font-mono text-sm font-semibold ${order.side === 'buy' ? 'text-trading-up' : 'text-trading-down'}`}>
                    {order.side.toUpperCase()}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted">Entry</p>
                  <p className="font-mono text-sm">{order.entry.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted">SL</p>
                  <p className="font-mono text-sm">{order.stop_loss.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted">TP</p>
                  <p className="font-mono text-sm">{order.take_profit.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted">RR</p>
                  <p className="font-mono text-sm text-primary">{order.risk_reward.toFixed(2)}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-8 text-center">
          <p className="text-sm text-muted">No active pending orders{selectedBot ? ` for ${selectedBot.name}` : ''}</p>
        </div>
      )}

      {/* Past orders */}
      {pastOrders.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Past Orders</h2>
          <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline-on-dark text-muted text-xs">
                  <th className="text-left p-3 font-medium">Bot</th>
                  <th className="text-left p-3 font-medium">Side</th>
                  <th className="text-right p-3 font-medium">Entry</th>
                  <th className="text-right p-3 font-medium">SL</th>
                  <th className="text-right p-3 font-medium">TP</th>
                    <th className="text-right p-3 font-medium">RR</th>
                    <th className="text-left p-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {pastOrders.map((o) => (
                  <tr key={o.id} className="border-b border-surface-elevated-dark">
                    <td className="p-3 text-xs text-muted font-mono">{o.bot_name ?? `#${o.bot_id}`}</td>
                    <td className={`p-3 font-mono text-xs font-semibold ${o.side === 'buy' ? 'text-trading-up' : 'text-trading-down'}`}>
                      {o.side.toUpperCase()}
                    </td>
                    <td className="p-3 font-mono text-xs text-right">{o.entry.toFixed(2)}</td>
                    <td className="p-3 font-mono text-xs text-right">{o.stop_loss.toFixed(2)}</td>
                    <td className="p-3 font-mono text-xs text-right">{o.take_profit.toFixed(2)}</td>
                    <td className="p-3 font-mono text-xs text-right">{o.risk_reward.toFixed(2)}</td>
                    <td className="p-3">
                      <span className="text-xs font-mono text-muted">{o.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Rejection log */}
      {rejections.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Rejection Log{selectedBot ? ` — ${selectedBot.name}` : ''}</h2>
          <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg">
            <div className="max-h-60 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline-on-dark text-muted text-xs sticky top-0 bg-surface-card-dark">
                  <th className="text-left p-3 font-medium">Time</th>
                  <th className="text-left p-3 font-medium">Bot</th>
                  <th className="text-left p-3 font-medium">Reason</th>
                </tr>
              </thead>
              <tbody>
                {rejections.map((r: any) => (
                  <tr key={r.id} className="border-b border-surface-elevated-dark">
                    <td className="p-3 text-xs text-muted font-mono">
                      {new Date((r.created_at ?? r.ts) * 1000).toLocaleTimeString()}
                    </td>
                    <td className="p-3 text-xs text-muted font-mono">{r.bot_name ?? `#${r.bot_id}`}</td>
                    <td className="p-3 text-xs text-muted">{r.reason ?? r.message ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
