import { useState, useEffect, useCallback } from 'react'
import client from '../api/client'
import type { PendingOrder } from '../types/api'

export default function PendingOrders() {
  const [orders, setOrders] = useState<PendingOrder[]>([])
  const [rejections, setRejections] = useState<any[]>([])
  const [state, setState] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    try {
      const [ordersRes, rejRes, stateRes] = await Promise.all([
        client.get<PendingOrder[]>('/pending-orders', { params: { limit: 50 } }),
        client.get<any[]>('/pending-orders/rejections', { params: { limit: 20 } }),
        client.get<any>('/pending-orders/state'),
      ])
      setOrders(ordersRes.data)
      setRejections(rejRes.data)
      setState(stateRes.data)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [])

  const cancelOrder = useCallback(async (orderId: number) => {
    try {
      await client.post(`/pending-orders/${orderId}/cancel`)
      fetchData()
    } catch {
      // ignore
    }
  }, [fetchData])

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

  const activeOrder = orders.find((o) => o.status === 'pending')

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-body">Pending Orders</h1>
        <button
          onClick={evaluateAll}
          className="px-3 py-1.5 text-xs rounded-md bg-primary/10 text-primary border border-primary/50 hover:bg-primary/20 transition-colors cursor-pointer"
        >
          Re-evaluate
        </button>
      </div>

      {state?.rules && (
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-4">
          <p className="text-xs text-muted mb-2 uppercase tracking-wider font-semibold">Rules</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            {Object.entries(state.rules).map(([key, val]) => (
              <div key={key}>
                <span className="text-muted">{key}: </span>
                <span className="text-body font-mono">{String(val)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeOrder && (
        <div className="bg-surface-card-dark border border-primary/30 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold text-primary uppercase tracking-wider">Active Pending Order</p>
            <button
              onClick={() => cancelOrder(activeOrder.id)}
              className="px-2.5 py-1 text-xs rounded bg-trading-down/10 text-trading-down border border-trading-down/50 hover:bg-trading-down/20 transition-colors cursor-pointer"
            >
              Cancel
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div>
              <p className="text-xs text-muted">Side</p>
              <p className={`font-mono text-sm font-semibold ${activeOrder.side === 'buy' ? 'text-trading-up' : 'text-trading-down'}`}>
                {activeOrder.side.toUpperCase()}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted">Entry</p>
              <p className="font-mono text-sm">{activeOrder.entry.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-xs text-muted">SL</p>
              <p className="font-mono text-sm">{activeOrder.stop_loss.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-xs text-muted">TP</p>
              <p className="font-mono text-sm">{activeOrder.take_profit.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-xs text-muted">RR</p>
              <p className="font-mono text-sm text-primary">{activeOrder.risk_reward.toFixed(2)}</p>
            </div>
          </div>
        </div>
      )}

      {!activeOrder && (
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-8 text-center">
          <p className="text-sm text-muted">No active pending orders</p>
        </div>
      )}

      {orders.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">All Pending Orders</h2>
          <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline-on-dark text-muted text-xs">
                  <th className="text-left p-3 font-medium">Side</th>
                  <th className="text-right p-3 font-medium">Entry</th>
                  <th className="text-right p-3 font-medium">SL</th>
                  <th className="text-right p-3 font-medium">TP</th>
                  <th className="text-right p-3 font-medium">RR</th>
                  <th className="text-left p-3 font-medium">Status</th>
                  <th className="text-left p-3 font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {orders.filter((o) => o.status !== 'pending').map((o) => (
                  <tr key={o.id} className="border-b border-surface-elevated-dark">
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
                    <td className="p-3">
                      {o.status === 'pending' && (
                        <button
                          onClick={() => cancelOrder(o.id)}
                          className="px-2 py-1 text-xs rounded bg-trading-down/10 text-trading-down border border-trading-down/50 cursor-pointer"
                        >
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {rejections.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Rejection Log</h2>
          <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg overflow-hidden max-h-60 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline-on-dark text-muted text-xs sticky top-0 bg-surface-card-dark">
                  <th className="text-left p-3 font-medium">Time</th>
                  <th className="text-left p-3 font-medium">Reason</th>
                </tr>
              </thead>
              <tbody>
                {rejections.map((r: any) => (
                  <tr key={r.id} className="border-b border-surface-elevated-dark">
                    <td className="p-3 text-xs text-muted font-mono">
                      {new Date((r.created_at ?? r.ts) * 1000).toLocaleTimeString()}
                    </td>
                    <td className="p-3 text-xs text-muted">{r.reason ?? r.message ?? '—'}</td>
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
