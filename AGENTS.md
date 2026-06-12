# MT5 Paper Trading Receiver - Agent Notes

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
          │  Bot "Paper Trading" (id=1)     │
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

### Key Changes in v2.0

| Before | After |
|--------|-------|
| `PaperEngine` (1 wallet) | Bot "Paper Trading" (id=1) via multibot |
| `PendingOrderEngine` | Multibot runtime `_evaluate_bot()` |
| `AutoPaperExecutionEngine` | Multibot `process_tick_sync()` |
| `multibot/db.py` (separate connection) | Uses `storage.py` shared connection |
| `runtime._trend()` (reimplemented) | Calls `indicators.compute_indicators()` |
| `execution._round_down()` / `runtime._round_lot()` | `runtime._round_lot()` (unified) |
| `app/strategies/` | Removed (dead code) |
| `api_key`, `strategy_enabled` config | Removed |

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

**MultiBot (execution layer):**
- `app/multibot/runtime.py` — Bot evaluation engine (`_evaluate_bot`, `process_tick_sync`)
- `app/multibot/service.py` — CRUD for profiles, bots, wallets
- `app/multibot/db.py` — Migration + schema for multibot tables
- `app/multibot/router.py` — MultiBot API endpoints
- `app/multibot/models.py` — Pydantic schemas
- `app/multibot/dashboard.py` — Embedded HTML dashboard

**Frontend**: React + TypeScript + Vite
- `frontend/` — React app with dashboard pages
- `dashboard/index.html` — Simple embedded dashboard (lightweight)

## Key Concepts

### Paper-Only System
- **Never** sends orders to real MT5
- Auto execution is OFF by default
- Enable with: `curl -X POST http://localhost:5050/api/strategy/enable`
- Legacy `/api/strategy/enable` now enables the "Paper Trading" bot (id=1)

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

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | System health + sender status |
| `/price` | POST | Ingest tick from MT5 sender |
| `/api/state` | GET | Full system state (tick, positions, indicators, orders) |
| `/api/trades` | GET | Trade history (Paper Trading bot) |
| `/api/candles/{timeframe}` | GET | Candle data |
| `/api/swings/{timeframe}` | GET | swing points |
| `/api/bos/{timeframe}` | GET | Break of structure events |
| `/api/order-blocks/{timeframe}` | GET | Order blocks |
| `/api/pending-orders/state` | GET | Pending order status |
| `/api/strategy/status` | GET | Strategy enabled status |
| `/api/strategy/enable` | POST | Enable auto execution |
| `/api/strategy/disable` | POST | Disable auto execution |
| `/api/paper/open` | POST | Open paper position (manual) |
| `/api/paper/close` | POST | Close paper position (manual) |
| `/api/paper/reset` | POST | Reset Paper Trading wallet |
| `/api/stats` | GET | Performance statistics |
| `/api/replay/run` | POST | Run replay simulation |
| `/api/replay/latest` | GET | Latest replay result |
| `/dashboard` | GET | Simple dashboard HTML |
| `/ws/ticks` | WS | Real-time tick streaming |
| `/api/profiles` | GET/POST | MultiBot profile management |
| `/api/bots` | GET/POST | MultiBot bot management |
| `/api/bots/{id}/state` | GET | Bot runtime state |
| `/api/bots/{id}/trades` | GET | Bot trade history |
| `/api/bots/{id}/wallet` | GET | Bot wallet info |
| `/ws/multibot` | WS | MultiBot real-time state |

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
curl -X POST http://localhost:5050/api/strategy/enable
```

### Disable Auto Paper Execution
```bash
curl -X POST http://localhost:5050/api/strategy/disable
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

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `sender_online: false` | MT5 sender not sending ticks | Check MT5 sender script |
| `websocket_clients: 0` | No dashboard connection | Refresh dashboard page |
| `strategy enabled but no fills` | OB not touched or bot not triggered | Check `api/bots/1/state` |
| `sqlite busy` | Concurrent write attempts | Back up DB, restart receiver |

## Version History

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
