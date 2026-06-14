import { create } from 'zustand'

export interface MarketTick {
  symbol: string
  bid: number
  ask: number
  spread: number
  seq: number
  timestamp: number
  mid: number
}

interface MarketState {
  ticks: Record<string, MarketTick>
  connected: boolean
  setTick: (symbol: string, tick: MarketTick) => void
  setConnected: (connected: boolean) => void
}

export const useMarketStore = create<MarketState>((set) => ({
  ticks: {},
  connected: false,
  setTick: (symbol, tick) =>
    set((state) => ({
      ticks: {
        ...state.ticks,
        [symbol.toUpperCase()]: tick,
      },
    })),
  setConnected: (connected) => set({ connected }),
}))
