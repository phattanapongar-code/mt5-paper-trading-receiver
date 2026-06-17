import { useEffect, useRef } from 'react'
import { hasAuth } from './client'
import { useMarketStore } from '../stores/useMarketStore'

type MessageHandler = (data: any) => void

// Module-level WebSocket singleton and listener registry
let globalWs: WebSocket | null = null
let retryTimer: ReturnType<typeof setTimeout> | null = null
let retryCount = 0
const listeners = new Set<MessageHandler>()

function connectGlobal() {
  if (globalWs || !hasAuth()) return

  if (retryTimer) {
    clearTimeout(retryTimer)
    retryTimer = null
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const url = `${protocol}//${host}/ws/ticks`

  const ws = new WebSocket(url)
  globalWs = ws

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      
      // 1. Sync real-time ticks to global Zustand store
      if (data?.tick?.symbol) {
        const t = data.tick
        useMarketStore.getState().setTick(t.symbol, {
          symbol: t.symbol,
          bid: t.bid,
          ask: t.ask,
          spread: t.spread,
          seq: t.seq,
          timestamp: t.timestamp,
          mid: t.mid ?? ((t.bid + t.ask) / 2)
        })
      }

      // 2. Broadcast to all active page/component listeners
      listeners.forEach((listener) => {
        try {
          listener(data)
        } catch (err) {
          console.error('WS Listener Error:', err)
        }
      })
    } catch {
      // ignore parse errors
    }
  }

  ws.onopen = () => {
    retryCount = 0
    useMarketStore.getState().setConnected(true)
  }

  ws.onclose = () => {
    globalWs = null
    useMarketStore.getState().setConnected(false)
    const delay = Math.min(3000 * Math.pow(2, retryCount), 30000)
    retryCount++
    retryTimer = setTimeout(connectGlobal, delay)
  }

  ws.onerror = () => {
    ws.close()
  }
}

function disconnectGlobal() {
  if (retryTimer) {
    clearTimeout(retryTimer)
    retryTimer = null
  }
  if (globalWs) {
    globalWs.onopen = null
    globalWs.onclose = null
    globalWs.onerror = null
    globalWs.onmessage = null
    if (globalWs.readyState === WebSocket.OPEN) {
      globalWs.close()
    }
    globalWs = null
  }
  useMarketStore.getState().setConnected(false)
}

export function useWebSocket(
  path: string,
  handler: MessageHandler,
  enabled = true
) {
  const handlerRef = useRef(handler)
  handlerRef.current = handler

  useEffect(() => {
    if (!enabled) return

    const listener = (data: any) => {
      handlerRef.current(data)
    }

    listeners.add(listener)
    connectGlobal()

    return () => {
      listeners.delete(listener)
      if (listeners.size === 0) {
        disconnectGlobal()
      }
    }
  }, [enabled])

  return { wsRef: { current: globalWs }, selectedBotId: null }
}
