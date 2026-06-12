import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import client, { setDefaultSymbol } from '../api/client'
import type { Bot } from '../types/api'

const BOT_STORAGE_KEY = 'mt5_selected_bot'
const SYMBOL_STORAGE_KEY = 'mt5_selected_symbol'

export interface BotContextType {
  allBots: Bot[]
  selectedBot: Bot | null
  setSelectedBot: (botId: number | null) => void
  symbol: string
  setSymbol: (s: string) => void
  symbols: string[]
  loading: boolean
}

const BotContext = createContext<BotContextType | null>(null)

const DEFAULT_SYMBOLS = ['XAUUSD', 'BTCUSD', 'ETHUSD', 'EURUSD', 'GBPUSD', 'USDCAD', 'USDJPY', 'AUDUSD', 'SPX500', 'NAS100']

export function BotProvider({ children }: { children: ReactNode }) {
  const [allBots, setAllBots] = useState<Bot[]>([])
  const [selectedBot, setSelectedBotState] = useState<Bot | null>(null)
  const [symbol, setSymbolState] = useState<string>(() => localStorage.getItem(SYMBOL_STORAGE_KEY) || 'XAUUSD')
  const [loading, setLoading] = useState(true)
  const [symbols, setSymbols] = useState<string[]>(DEFAULT_SYMBOLS)

  // Sync symbol to client default + localStorage
  const setSymbol = useCallback((s: string) => {
    setSymbolState(s)
    setDefaultSymbol(s)
    localStorage.setItem(SYMBOL_STORAGE_KEY, s)
  }, [])

  useEffect(() => {
    setDefaultSymbol(symbol)
  }, []) // only on mount

  useEffect(() => {
    client.get<Bot[]>('/bots').then((res) => {
      const bots = res.data.sort((a, b) => a.id - b.id)
      setAllBots(bots)
      const storedId = localStorage.getItem(BOT_STORAGE_KEY)
      if (storedId) {
        const found = bots.find((b) => b.id === Number(storedId))
        if (found) setSelectedBotState(found)
      }
    }).catch(() => {
      // ignore fetch errors
    }).finally(() => {
      setLoading(false)
    })

    // Fetch available symbols from backend
    client.get<{ symbols: string[] }>('/symbols').then(res => {
      if (res.data.symbols?.length) setSymbols(res.data.symbols)
    }).catch(() => {})
  }, [])

  const setSelectedBot = useCallback((botId: number | null) => {
    if (botId === null) {
      setSelectedBotState(null)
      localStorage.removeItem(BOT_STORAGE_KEY)
    } else {
      const bot = allBots.find((b) => b.id === botId)
      if (bot) {
        setSelectedBotState(bot)
        localStorage.setItem(BOT_STORAGE_KEY, String(botId))
      }
    }
  }, [allBots])

  return (
    <BotContext.Provider value={{ allBots, selectedBot, setSelectedBot, symbol, setSymbol, symbols, loading }}>
      {children}
    </BotContext.Provider>
  )
}

export function useBotContext() {
  const ctx = useContext(BotContext)
  if (!ctx) throw new Error('useBotContext must be used within BotProvider')
  return ctx
}
