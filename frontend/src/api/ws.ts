import React, { useEffect, useRef, useCallback } from 'react'
import { hasAuth } from './client'
import { useBotContext } from '../context/BotContext'

type MessageHandler = (data: unknown) => void
type HandlersMap = Record<string, (data: any) => void>

// Overload: classic single callback
export function useWebSocket(
  path: string,
  onMessage: MessageHandler,
  enabled?: boolean,
): { wsRef: React.RefObject<WebSocket | null>; selectedBotId: number | null }

// Overload: typed handlers by message type
export function useWebSocket(
  path: string,
  handlers: HandlersMap,
  enabled?: boolean,
): { wsRef: React.RefObject<WebSocket | null>; selectedBotId: number | null }

// Implementation
export function useWebSocket(
  path: string,
  handler: MessageHandler | HandlersMap,
  enabled = true,
) {
  const wsRef = useRef<WebSocket | null>(null)
  const handlerRef = useRef(handler)
  const intentionalCloseRef = useRef(false)
  const retryCountRef = useRef(0)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const { selectedBot } = useBotContext()
  handlerRef.current = handler

  const connect = useCallback(() => {
    if (!enabled || !hasAuth()) return

    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current)
      retryTimerRef.current = null
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}${path}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        const h = handlerRef.current
        if (typeof h === 'function') {
          h(data)
        } else if (data?.type && h[data.type]) {
          h[data.type](data)
        }
      } catch {
        // ignore parse errors
      }
    }

    ws.onopen = () => {
      retryCountRef.current = 0
    }

    ws.onclose = () => {
      if (!intentionalCloseRef.current) {
        wsRef.current = null
        const attempt = retryCountRef.current
        const delay = Math.min(3000 * Math.pow(2, attempt), 30000)
        retryCountRef.current = attempt + 1
        retryTimerRef.current = setTimeout(connect, delay)
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [path, enabled])

  useEffect(() => {
    intentionalCloseRef.current = false
    connect()
    return () => {
      intentionalCloseRef.current = true
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current)
        retryTimerRef.current = null
      }
      const ws = wsRef.current
      if (ws) {
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
          ws.close()
        }
        wsRef.current = null
      }
    }
  }, [connect])

  return { wsRef, selectedBotId: selectedBot?.id ?? null }
}
