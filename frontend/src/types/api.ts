export interface Tick {
  type: string
  symbol: string
  bid: number
  ask: number
  mid: number
  spread: number
  timestamp: number
  source_timestamp: number
  seq: number
  received_at: number
}

export interface Candle {
  id: number
  symbol: string
  timeframe: string
  open_time: number
  close_time: number
  open: number
  high: number
  low: number
  close: number
  tick_count: number
  is_closed: boolean
}

export interface Indicators {
  ma60: number | null
  ma80: number | null
  ma300: number | null
  atr14: number | null
  avg_body20: number | null
  trend: string | null
}

export interface PaperAccount {
  balance: number
  equity: number
  unrealized_pnl: number
  realized_pnl: number
  open_position: Trade | null
}

export interface Trade {
  id: number
  symbol: string
  side: string
  lot: number
  entry: number
  exit: number | null
  stop_loss: number | null
  take_profit: number | null
  pnl: number | null
  r_multiple: number | null
  status: string
  opened_at: number
  closed_at: number | null
  exit_reason: string | null
  note: string | null
}

export interface MarketStructureState {
  symbol: string
  timeframe: string
  swing_window: number
  latest_swing_high: { price: number; side: string; pivot_open_time: number } | null
  latest_swing_low: { price: number; side: string; pivot_open_time: number } | null
  latest_bos: { side: string; break_close: number; created_at: number } | null
  counts: { swings: number; bos: number }
}

export interface BosEvent {
  id: number
  side: string
  break_open_time: number
  break_close: number
  created_at: number
}

export interface OrderBlock {
  id: number
  side: string
  ob_open: number
  ob_close: number
  ob_low: number
  ob_high: number
  score: number
  is_strong: boolean
  status: string
  retest_count: number
}

export interface OrderBlockState {
  strong_count: number
  active_total: number
}

export interface PendingOrder {
  id: number
  side: string
  entry: number
  stop_loss: number
  take_profit: number
  risk_reward: number
  status: string
  created_at: number
  expires_at: number
}

export interface PendingOrderState {
  active: PendingOrder | null
  rules: Record<string, unknown>
}

export interface ExecutionState {
  enabled: boolean
  auto_paper_enabled: boolean
}

export interface Stats {
  closed_trades: number
  wins: number
  losses: number
  win_rate: number | null
  profit_factor: number | null
  net_pnl: number
  max_drawdown_usd: number | null
  average_r: number | null
}

export interface Health {
  ok: boolean
  sender_online: boolean
  last_received_at: number | null
  seconds_since_last_message: number | null
  last_seq: number | null
  strategy_enabled: boolean
  websocket_clients: number
}

export interface AppState {
  health: Health
  latest_tick: Tick | null
  paper: PaperAccount
  indicators: Record<string, Indicators>
  market_structure: Record<string, MarketStructureState>
  order_blocks: Record<string, OrderBlockState>
  pending_orders: PendingOrderState
  execution: ExecutionState
  stats: Stats
}

// Multi-bot types
export interface Profile {
  id: number
  name: string
  description: string | null
  enabled: number
  bot_count: number
  total_balance: number
  total_realized_pnl: number
  created_at: number
}

export interface Bot {
  id: number
  profile_id: number
  name: string
  strategy_type: string
  strategy_version: string
  symbol: string
  timeframe: string
  enabled: boolean
  parameters: Record<string, unknown>
  created_at: number
}

export interface BotStats {
  closed_trades: number
  wins: number
  losses: number
  net_pnl: number
  max_drawdown_usd: number
}

export interface BotState {
  bot: Bot
  pending: PendingOrder | null
  position: Trade | null
  runtime: {
    latest_trend: string | null
    consecutive_losses: number
    daily_realized_pnl: number
    paused_reason: string | null
  } | null
  trades: Trade[]
}

export interface Wallet {
  id: number
  bot_id: number
  initial_balance: number
  balance: number
  realized_pnl: number
  currency: string
  max_drawdown: number
  peak_equity: number
}

export interface CompareResult {
  bot_id: number
  name: string
  total_trades: number
  win_rate: number
  total_pnl: number
  profit_factor: number
}

export interface BotSignalLog {
  id: number
  symbol?: string
  timeframe?: string
  bot_id?: number
  event_type: string
  message: string
  payload_json?: string | null
  payload?: string
  created_at: number
  ts?: number
}

export interface BotCreateRequest {
  profile_id: number
  name: string
  strategy_type?: string
  strategy_version?: string
  symbol?: string
  timeframe?: string
  enabled?: boolean
  initial_balance?: number
  parameters?: Record<string, unknown>
}

export interface ProfileCreateRequest {
  name: string
  description?: string
  enabled?: boolean
}

export interface CompareBot {
  bot_id: number
  name: string
  profile_name: string
  strategy_type: string
  strategy_version: string
  symbol: string
  timeframe: string
  initial_balance: number
  balance: number
  realized_pnl: number
  max_drawdown: number
  closed_trades: number
  open_positions: number
  pending_orders: number
  wins: number
  net_pnl: number
  win_rate: number
}

export interface ReplayRun {
  id: number
  symbol: string
  payload: string
  created_at: number
}

export interface HistoryCandle {
  open_time: number
  open: number
  high: number
  low: number
  close: number
  tick_volume?: number
}

export interface HistoryImportRequest {
  symbol: string
  timeframe: 'M1' | 'M5' | 'M15' | 'H1'
  source: string
  offset_seconds: number
  candles: HistoryCandle[]
}

export interface HistoryStatus {
  symbol: string
  closed_candles: Record<string, number>
  latest_import: {
    id: number
    symbol: string
    source: string
    timeframe: string
    offset_seconds: number
    imported_m1?: number
    rebuilt_m5: number
    rebuilt_m15: number
    rebuilt_h1: number
    created_at: number
  } | null
}
