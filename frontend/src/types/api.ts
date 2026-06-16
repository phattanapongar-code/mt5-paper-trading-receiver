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
  rsi14: number | null
  macd: number | null
  macd_signal: number | null
  macd_histogram: number | null
  bb_upper: number | null
  bb_middle: number | null
  bb_lower: number | null
}

export interface BacktestResult {
  ok: boolean
  total_trades: number
  wins: number
  losses: number
  win_rate: number
  net_pnl: number
  gross_profit: number
  gross_loss: number
  profit_factor: number
  sharpe_ratio: number
  max_drawdown_pct: number
  avg_r: number
  total_r: number
  final_balance: number
  return_pct: number
  equity_curve: { time: number; equity: number }[]
  trades: Trade[]
  run_id?: number
}

export interface BacktestHistory {
  id: number
  strategy_type: string
  symbol: string
  timeframe: string
  start_time: number
  end_time: number
  total_trades: number
  net_pnl: number
  win_rate: number
  profit_factor: number
  sharpe_ratio: number
  max_drawdown_pct: number
  return_pct: number
  created_at: number
}

export interface OptimizeResult {
  ok: boolean
  strategy_type: string
  param_ranges: Record<string, unknown>
  total_combinations: number
  optimization_metric: string
  results: Record<string, unknown>[]
  run_id?: number
}

export interface AlertConfig {
  bot_token: string
  chat_id: string
  enabled: boolean
  enabled_categories: string[]
}

export interface Trade {
  id: number
  bot_id: number
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
  // Execution realism fields
  commission?: number
  slippage?: number
  spread_cost?: number
  net_pnl?: number
  execution_detail?: string
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

export interface Health {
  ok: boolean
  sender_online: boolean
  last_received_at: number | null
  seconds_since_last_message: number | null
  last_seq: number | null
  websocket_clients: number
  latest_tick: Tick | null
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
  runtime_updated_at?: number
}

export interface BotStats {
  closed_trades: number
  wins: number
  losses: number
  win_rate: number
  gross_pnl?: number
  net_pnl: number
  total_commission?: number
  total_spread_cost?: number
  total_slippage?: number
  profit_factor?: number | null
  average_r?: number
  max_drawdown_usd: number
  balance?: number
  realized_pnl?: number
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
    updated_at: number | null
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
  total_commission?: number
  total_spread_cost?: number
  total_slippage?: number
}

export interface BotCosts {
  total_commission: number
  total_spread_cost: number
  total_slippage: number
  total_costs: number
  trades_with_costs: {
    commission: number
    slippage: number
    spread_cost: number
    pnl_gross: number
    pnl_net: number
  }[]
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

export interface StrategyOption {
  id: string
  name: string
  description: string
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

// ── Real Trading Types (trader.py) ──

export interface TraderHealth {
  ok: boolean
  connected: boolean
  terminal: string | null
  terminal_version: number | null
  account: {
    login: number | null
    balance: number | null
    equity: number | null
    margin: number | null
    margin_free: number | null
    margin_level: number | null
    leverage: number | null
    currency: string | null
    name: string | null
    server: string | null
  } | null
  symbols: string[]
  queue_size: number
  error: string | null
}

export interface TraderAccount {
  ok: boolean
  login: number
  balance: number
  equity: number
  margin: number
  margin_free: number
  margin_level: number
  leverage: number
  currency: string
  name: string
  server: string
  trade_allowed: boolean
  trade_expert: boolean
}

export interface TraderPosition {
  ticket: number
  symbol: string
  type: 'buy' | 'sell'
  volume: number
  open_price: number
  sl: number | null
  tp: number | null
  profit: number
  commission: number
  swap: number
  open_time: number
  magic: number
  comment: string
}

export interface TraderPositionsResponse {
  ok: boolean
  positions: TraderPosition[]
  count: number
}

export interface TradeOpenRequest {
  symbol: string
  type: 'buy' | 'sell'
  volume: number
  sl?: number
  tp?: number
  sl_pips?: number
  tp_pips?: number
  comment?: string
  magic?: number
}

export interface TradeResult {
  ok: boolean
  ticket?: number
  price?: number
  volume?: number
  sl?: number
  tp?: number
  error?: string
  error_code?: number
  queued?: boolean
}

export interface TraderSymbolsResponse {
  symbols: string[]
}

export interface TraderSymbolInfo {
  symbol: string
  description: string
  digits: number
  volume_min: number
  volume_max: number
  volume_step: number
  point: number
  contract_size: number
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
