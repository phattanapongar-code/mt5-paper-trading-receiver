# MT5 Paper Trading Receiver - Agent Notes

## Golden Rules

1. **ห้ามเดา — ไม่รู้ให้ถามก่อนเสมอ**
   - ถ้าไม่แน่ใจเลข จำนวน ราคา คอนฟิก หรือรายละเอียดอะไร → ถาม user ก่อน
   - ห้ามสมมติว่า broker มีกี่ symbol, MT5 build เท่าไหร่, settings อะไร
   - ห้ามเดา API behavior, error codes, หรือผลลัพท์ของระบบอื่น

2. **คิดเผื่อหน้าบ้านทุกครั้ง**
   - เมื่อสร้าง/แก้ API endpoint ไหน → คิดเสมอว่าหน้าบ้านต้องทำอะไรบ้าง
   - ทุก endpoint ที่เพิ่ม → ต้องมี proxy ใน main.py + type ใน api.ts
   - เวลาเพิ่ม backend feature → เพิ่ม frontend component ให้ครบในรอบเดียวกัน

3. **ทุกคำสั่งให้ถามก่อนถ้ามีทางเลือก**
   - Flask vs FastAPI, SQLite vs JSON, port number, naming convention
   - อย่าเลือกเอง — เสนอ options แล้วให้ user ตัดสินใจ

## Quick Start

```bash
cd ~/Documents/Hermess/mt5-paper-trading-receiver
source .venv/bin/activate
python run.py
```

Dashboard: `http://localhost:5050/dashboard`

## Architecture Overview (v2.0 — Unified)

**Backend**: FastAPI + SQLite + Python

### Unified Architecture (refactored v2.0)

```
MT5 Sender → /price endpoint
                  │
          ┌───────┴──────────────────┐
          │     SHARED ANALYSIS      │
          │  CandleEngine            │
          │  MarketStructureEngine   │
          │  OrderBlockEngine        │
          │  indicators.py           │
          └───────┬──────────────────┘
                  │ (same data for all bots)
                  ▼
          ┌─────────────────────────────────┐
          │     MULTIBOT RUNTIME            │
          │  process_tick_sync()            │
          │                                 │
          │  Bot "Paper Trading" (id varies) │
          │    ├ Wallet #1 (balance=$500)    │
          │    ├ bot_positions               │
          │    └ bot_pending_orders          │
          │                                 │
          │  Bot #2 → Wallet #2             │
          │  Bot #3 → Wallet #3             │
          └─────────────────────────────────┘
                  │
          DB Layer: storage.py (shared singleton)
          SQLite WAL mode + RLock
```

### Key Changes (v2.0 → v2.5)

| Before (v1.x) | After (v2.5) |
|--------|-------|
| `PaperEngine` (1 wallet) | Bot "Paper Trading" via multibot |
| `PendingOrderEngine` | Multibot runtime `_evaluate_bot()` |
| `AutoPaperExecutionEngine` | Multibot `process_tick_sync()` |
| `multibot/db.py` (separate connection) | Uses `storage.py` shared connection |
| `runtime._trend()` (reimplemented) | Calls `indicators.compute_indicators()` |
| `execution._round_down()` / `runtime._round_lot()` | `runtime._round_lot()` (unified) |
| `app/strategies/` | Removed (dead code) |
| `api_key`, `strategy_enabled` config | Removed |
| 1 strategy (trend_ob) | 5 strategies (trend_ob, bb_breakout, ma_cross, macd_cross, rsi_meanrev) |
| No Telegram alerts | `AlertEngine` with Telegram notifications |
| No backtest | `app/backtest/` engine + optimizer |

### Files

**Core (shared analysis):**
- `app/main.py` — REST/WS endpoints, tick ingestion pipeline
- `app/config.py` — Settings via environment variables
- `app/storage.py` — SQLite singleton connection (WAL mode + RLock)
- `app/candle_engine.py` — Timeframe resampling (M1→M5→M15→H1)
- `app/order_blocks.py` — Strong Order Block detection
- `app/market_structure.py` — Swing points, BOS detection
- `app/indicators.py` — Indicators (SMA, ATR, trend detection)
- `app/stats.py` — PnL, equity curve, win rate (backed by bot_positions)
- `app/replay.py` — Historical replay preview
- `app/alert.py` — Telegram AlertEngine (dedicated event loop thread)

**MultiBot (execution layer):**
- `app/multibot/runtime.py` — Bot evaluation engine (`_evaluate_bot`, `process_tick_sync`)
- `app/multibot/service.py` — CRUD for profiles, bots, wallets
- `app/multibot/db.py` — Migration + schema for multibot tables
- `app/multibot/router.py` — MultiBot API endpoints
- `app/multibot/models.py` — Pydantic schemas
- `app/multibot/strategies/` — Strategy implementations (trend_ob, bb_breakout, ma_cross, macd_cross, rsi_meanrev)

**Backtest (v2.5.0):**
- `app/backtest/engine.py` — Historical simulation engine
- `app/backtest/report.py` — Performance report generator
- `app/backtest/optimizer.py` — Parameter grid search
- `app/backtest/models.py` — Pydantic request schemas
- `app/backtest/router.py` — Backtest API endpoints

**Frontend**: React + TypeScript + Vite
- `frontend/` — React SPA (replaces old embedded dashboard)

## Key Concepts

### Paper-Only System
- **Never** sends orders to real MT5
- Auto execution is OFF by default (all bots start disabled)
- Enable a bot with: `curl -X POST http://localhost:5050/api/bots/{bot_id}/enable`

### Tick Pipeline
```
MT5 sender → /price endpoint → tick ingestion → candle bucketing → 
market structure refresh → order block refresh → process_tick_sync(all bots) → 
WebSocket broadcast
```

### Bot System
- Every bot has its own wallet (`wallets` table)
- Every bot has its own positions (`bot_positions` table) and pending orders (`bot_pending_orders`)
- All bots share the same market analysis (candles, OBs, swings)
- Strategy logic is shared: trend-following + OB retest (same across all bots)
- Parameters (risk, RR, expiry, etc.) are per-bot

### Timeframes
- Supported: `M1`, `M5`, `M15`, `H1`
- All candles are closed at timeframe end (e.g., M15 closes at :15, :30, :45, :00)

### Order Block Scoring
- Strong OB has score ≥ 6
- Based on: BOS confirmation, impulse strength, swing alignment
- M15 OB candidates trigger M15 pending orders when price touches

### Pending Orders
- M15-only limit order candidates
- Entry at strong OB zone, SL beyond opposite swing
- TP at 2.0R minimum, expiry after 8 candles
- Single active pending order per symbol (cancels stale ones)

## Configuration (Environment Variables)

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_HOST` | `0.0.0.0` | Server host |
| `APP_PORT` | `5050` | Server port |
| `DB_PATH` | `data/receiver.sqlite3` | SQLite database path |
| `SYMBOL` | `XAUUSD` | Trading symbol |
| `INITIAL_BALANCE` | `500.0` | Paper account starting balance |
| `AUTO_PAPER_ENABLED` | `false` | Enable auto-paper execution |
| `MAX_SPREAD` | `1.5` | Max allowed spread (pips) |
| `PENDING_TIMEFRAME` | `M15` | Pending order timeframe |
| `PENDING_EXPIRY_CANDLES` | `8` | Pending order expiry (candles) |
| `PENDING_MIN_RR` | `1.5` | Minimum risk-reward |
| `PENDING_TP_R_MULTIPLE` | `2.0` | TP target in R multiples |
| `PENDING_SL_BUFFER_RATIO` | `0.30` | SL buffer as % of ATR |
| `TREND_RISK_PERCENT` | `0.01` | Risk per trade (% of equity) |
| `CONTRACT_SIZE` | `100.0` | Contract size per lot |
| `LOT_STEP` | `0.01` | Minimum lot increment |
| `MIN_LOT` | `0.01` | Minimum lot size |
| `MAX_LOT` | `10.0` | Maximum lot size |
| `DASHBOARD_USERNAME` | `admin` | Dashboard basic auth username |
| `DASHBOARD_PASSWORD` | `admin` | Dashboard basic auth password |
| `COMMISSION_PER_LOT` | `3.5` | Commission per lot (fixed) |
| `COMMISSION_TYPE` | `fixed` | Commission type (`fixed` or `percentage`) |
| `COMMISSION_PCT` | `0.0001` | Commission % (if type=`percentage`) |
| `SLIPPAGE_SIGMA` | `0.15` | Slippage Gaussian sigma (pips) |
| `SLIPPAGE_MAX_PIPS` | `0.5` | Max slippage (pips) |
| `LATENCY_MS_MIN` | `10` | Min latency simulation (ms) |
| `LATENCY_MS_MAX` | `50` | Max latency simulation (ms) |
| `GAP_CHECK_ENABLED` | `true` | Enable gap detection |
| `GAP_MAX_PERCENT` | `0.5` | Max gap adjustment (%) |
| `GAP_THRESHOLD_SECONDS` | `3600` | Gap threshold (seconds) |

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | System health + sender status |
| `/price` | POST | Ingest tick from MT5 sender |
| `/symbols` | GET | List available symbols |
| `/api/ticks` | GET | Recent tick history |
| `/api/candles/{timeframe}` | GET | Candle data |
| `/api/indicators/{timeframe}` | GET | Computed indicators (SMA, ATR, trend) |
| `/api/swings/{timeframe}` | GET | Swing points |
| `/api/bos/{timeframe}` | GET | Break of structure events |
| `/api/market-structure/{timeframe}` | GET | Market structure state |
| `/api/market-structure/rebuild` | POST | Rebuild market structure |
| `/api/order-blocks/active/{timeframe}` | GET | Active order blocks |
| `/api/order-blocks/state/{timeframe}` | GET | Order block state summary |
| `/api/order-blocks/rebuild` | POST | Rebuild order blocks |
| `/api/pending-orders` | GET | Pending orders list |
| `/api/pending-orders/rejections` | GET | Rejected pending orders |
| `/api/pending-orders/evaluate` | POST | Force evaluate pending orders |
| `/api/pending-orders/{id}/cancel` | POST | Cancel a pending order |
| `/api/trades` | GET | Trade history (filterable by bot_id/side/symbol) |
| `/api/signal-logs` | GET | Bot signal logs |
| `/api/bots/{id}/open` | POST | Open manual position |
| `/api/bots/{id}/close` | POST | Close manual position |
| `/api/bots/{id}/stats` | GET | Bot performance stats |
| `/api/bots/{id}/stats/equity` | GET | Bot equity curve |
| `/api/bots/{id}/stats/pnl-by-day` | GET | Bot daily PnL breakdown |
| `/api/replay/run` | POST | Run replay simulation |
| `/api/replay/latest` | GET | Latest replay result |
| `/api/history/import` | POST | Import historical data |
| `/api/history/status` | GET | Import status |
| `/ws/ticks` | WS | Real-time tick streaming |
| `/api/profiles` | GET/POST | MultiBot profile management |
| `/api/profiles/{id}/enable` | POST | Enable profile |
| `/api/profiles/{id}/disable` | POST | Disable profile |
| `/api/profiles/{id}` | DELETE | Delete profile |
| `/api/bots` | GET/POST | MultiBot bot management |
| `/api/bots/{id}` | GET/PUT/DELETE | Bot CRUD |
| `/api/bots/{id}/state` | GET | Bot runtime state |
| `/api/bots/{id}/trades` | GET | Bot trade history |
| `/api/bots/{id}/signals` | GET | Bot signal logs |
| `/api/bots/{id}/clone` | POST | Clone bot |
| `/api/bots/{id}/enable` | POST | Enable bot |
| `/api/bots/{id}/disable` | POST | Disable bot |
| `/api/bots/{id}/parameters` | PUT | Update bot parameters |
| `/api/bots/{id}/rename` | PUT | Rename bot |
| `/api/bots/{id}/wallet` | GET | Bot wallet info |
| `/api/bots/{id}/wallet/reset` | POST | Reset bot wallet |
| `/api/bots/{id}/costs` | GET | Bot execution costs breakdown |
| `/api/strategies` | GET | List available strategies |
| `/api/compare` | GET | Compare all bots |
| `/api/multibot/migration/status` | GET | Migration status |
| `/api/multibot/runtime/status` | GET | Runtime status |
| `/ws/multibot` | WS | MultiBot real-time state |
| `/api/backtest/run` | POST | Run backtest |
| `/api/backtest/optimize` | POST | Run parameter optimization |
| `/api/backtest/history` | GET | Backtest history |
| `/api/backtest/runs/{id}` | GET | Backtest run details |
| `/api/backtest/optimize/history` | GET | Optimization history |
| `/api/backtest/optimize/runs/{id}` | GET | Optimization run details |
| `/api/backtest/clone-bot/{run_id}` | POST | Clone bot from backtest |
| `/api/alerts/config` | GET/POST | Telegram alert configuration |
| `/api/alerts/test` | POST | Test Telegram alert |

## Testing

```bash
# Run all tests
python -m pytest

# Run specific test file  
python -m pytest tests/test_pending_orders.py
```

## Important Constraints

1. **Database**: SQLite with WAL mode. Single shared connection via `storage.get_conn()`
2. **Thread Safety**: RLock-based writer lock in `storage.py`
3. **Auto Execution is Paper-Only**: Never sends real MT5 orders
4. **Single Active Pending Order**: Per bot, stale candidates cancel
5. **Replay is Research Preview**: Based on M1 OHLC bars, not tick-perfect

## Common Tasks

### Enable Auto Paper Execution
```bash
curl -X POST http://localhost:5050/api/bots/{bot_id}/enable
```

### Disable Auto Paper Execution
```bash
curl -X POST http://localhost:5050/api/bots/{bot_id}/disable
```

### Create a New Bot
```bash
curl -X POST http://localhost:5050/api/bots \
  -H "Content-Type: application/json" \
  -d '{"profile_id":1,"name":"My Bot","initial_balance":1000}'
```

### Rebuild Market Structure
```bash
curl -X POST http://localhost:5050/api/market-structure/rebuild
```

### Rebuild Order Blocks
```bash
curl -X POST http://localhost:5050/api/order-blocks/rebuild
```

### Run Replay
```bash
curl -X POST http://localhost:5050/api/replay/run
curl http://localhost:5050/api/replay/latest
```

### Backup Database
```bash
./scripts/backup_db.sh
```

### Trigger WebSocket Broadcast (Debug)
```bash
curl -X POST http://localhost:5050/price -H "Content-Type: application/json" -d '{"type":"heartbeat","symbol":"XAUUSD","bid":2300.0,"ask":2300.5,"timestamp":'$(date +%s)',"seq":1}'
```

## Frontend Notes

- `dashboard/index.html` is the lightweight dashboard (embedded in backend)
- `frontend/` is the React dashboard with multi-bot support
- Both connect to the same REST/WS endpoints
- Frontend requires `/api/` endpoints to have Basic Auth (`admin:admin` by default)

## Testing

```bash
# Run all tests
python -m pytest

# Run specific test file  
python -m pytest tests/test_pending_orders.py
```

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `sender_online: false` | MT5 sender not sending ticks | Check MT5 sender script |
| `websocket_clients: 0` | No dashboard connection | Refresh dashboard page |
| `strategy enabled but no fills` | OB not touched or bot not triggered | Check `api/bots/{id}/state` |
| `sqlite busy` | Concurrent write attempts | Back up DB, restart receiver |

## Version History

- **v2.5.0**: Backtest engine + optimizer + report generator
  - 3 new strategies: BB breakout, MA cross, MACD cross, RSI mean reversion
  - Telegram AlertEngine with trade/risk/health notifications
  - Trailing stop (per-bot configurable)
  - Prop firm grade execution realism (Gaussian slippage, commission, spread cost, latency, gap detection)
  - Execution detail JSON tracking
- **v2.4.0**: Polish release
  - Mobile responsive sidebar (hamburger overlay on small screens)
  - Request dedup + cache (2s TTL on GET requests, auto-return cached data)
  - Dark/Light theme toggle in sidebar (persisted to localStorage)
  - Drawing tools on chart (trendline, horizontal, vertical, rectangle, ray + color picker + delete)
- **v2.3.0**: Bug fix + feature release
  - Per-bot savepoint isolation (one bot crash no longer kills all bots)
  - Charts: MA lines now compute SMA from candle data, different colors per MA, price line leak fixed
  - PnLDistribution: histogram timestamp bug fixed
  - Error Boundary + 404 page + Toast notification system
  - Replay page routed
  - Multi-symbol query params on all endpoints
  - Keyboard shortcuts (1-9,0,b), CSV export, position sizing calculator
  - Pending order countdown timer
  - Per-bot health check in /health
  - CSS theme cleanup: all undefined variables added
  - Embedded dashboard (`dashboard/index.html`) removed (React SPA replaces it)
- **v2.0**: Architecture refactor — unified DB, merged PaperEngine → MultiBot, removed legacy engines
- **v1.2.1**: Dashboard price hotfix (XAUUSD Bid/Ask/Mid/Spread/Tick age)
- **v1.2**: Multi-bot runtime fan-out
- **v1.1**: Multi-bot router foundation
- **Final Build**: Paper-only execution, auto fill, replay preview
