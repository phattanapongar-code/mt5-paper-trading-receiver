import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import client from '../api/client'
import type { Bot } from '../types/api'

const STORAGE_KEY = 'mt5_selected_bot'

export interface BotContextType {
  allBots: Bot[]
  selectedBot: Bot | null
  setSelectedBot: (botId: number | null) => void
  loading: boolean
}

const BotContext = createContext<BotContextType | null>(null)

export function BotProvider({ children }: { children: ReactNode }) {
  const [allBots, setAllBots] = useState<Bot[]>([])
  const [selectedBot, setSelectedBotState] = useState<Bot | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    client.get<Bot[]>('/bots').then((res) => {
      const bots = res.data.sort((a, b) => a.id - b.id)
      setAllBots(bots)
      const storedId = localStorage.getItem(STORAGE_KEY)
      if (storedId) {
        const found = bots.find((b) => b.id === Number(storedId))
        if (found) setSelectedBotState(found)
      }
    }).catch(() => {
      // ignore fetch errors
    }).finally(() => {
      setLoading(false)
    })
  }, [])

  const setSelectedBot = useCallback((botId: number | null) => {
    if (botId === null) {
      setSelectedBotState(null)
      localStorage.removeItem(STORAGE_KEY)
    } else {
      const bot = allBots.find((b) => b.id === botId)
      if (bot) {
        setSelectedBotState(bot)
        localStorage.setItem(STORAGE_KEY, String(botId))
      }
    }
  }, [allBots])

  return (
    <BotContext.Provider value={{ allBots, selectedBot, setSelectedBot, loading }}>
      {children}
    </BotContext.Provider>
  )
}

export function useBotContext() {
  const ctx = useContext(BotContext)
  if (!ctx) throw new Error('useBotContext must be used within BotProvider')
  return ctx
}
