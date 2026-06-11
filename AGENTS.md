# MT5 Paper Trading Receiver - Agent Notes

## Quick Start

```bash
cd ~/Documents/Hermess/mt5-paper-trading-receiver
source .venv/bin/activate
python run.py
```

Dashboard: `http://localhost:5050/dashboard`

## Architecture Overview

**Backend**: FastAPI + SQLite + Python
- `app/main.py` - REST/WS endpoints, tick ingestion pipeline
- `app/config.py` - Settings via environment variables
- `app/storage.py` - SQLite database (WAL mode)
- `app/candle_engine.py` - Timeframe resampling (M1→M5→M15→H1)
- `app/paper_engine.py` - Paper trading simulation
- `app/pending_orders.py` - M15 limit order candidates
- `app/order_blocks.py` - Strong Order Block detection
- `app/market_structure.py` - Swing points, BOS detection
- `app/execution.py` - Auto-paper execution (OFF by default)
- `app/stats.py` - PnL, equity curve, win rate
- `app/replay.py` - Historical replay preview
- `app/multibot/` - Multi-bot routing (v1.2)

**Frontend**: React + TypeScript + Vite
- `frontend/` - React app with dashboard pages
- `dashboard/index.html` - Simple embedded dashboard (lightweight)

## Key Concepts

### Paper-Only System
- **Never** sends orders to real MT5
- Auto execution is OFF by default
- Enable with: `curl -X POST http://localhost:5050/api/strategy/enable`

### Tick Pipeline
```
MT5 sender → /price endpoint → tick ingestion → candle bucketing → 
market structure refresh → order block refresh → pending order analysis → 
auto execution (if enabled) → WebSocket broadcast
```

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
| `STRATEGY_ENABLED` | `false` | Legacy flag (use auto_paper_enabled) |
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
| `/api/trades` | GET | Trade history |
| `/api/candles/{timeframe}` | GET | Candle data |
| `/api/swings/{timeframe}` | GET | swing points |
| `/api/bos/{timeframe}` | GET | Break of structure events |
| `/api/order-blocks/{timeframe}` | GET | Order blocks |
| `/api/pending-orders/state` | GET | Pending order status |
| `/api/strategy/status` | GET | Strategy enabled status |
| `/api/strategy/enable` | POST | Enable auto execution |
| `/api/strategy/disable` | POST | Disable auto execution |
| `/api/stats` | GET | Performance statistics |
| `/api/replay/run` | POST | Run replay simulation |
| `/api/replay/latest` | GET | Latest replay result |
| `/dashboard` | GET | Simple dashboard HTML |
| `/ws/ticks` | WS | Real-time tick streaming |

## Testing

```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/test_pending_orders.py

# Run with coverage
python -m pytest --cov=app --cov-report=term-missing
```

## Important Constraints

1. **Database**: SQLite with WAL mode. Back up with `./scripts/backup_db.sh`
2. **No Multi-Thread Safety**: Single writer lock in `storage.py` (RLock-based)
3. **Auto Execution is Paper-Only**: Never sends real MT5 orders
4. **Single Active Pending Order**: Stale candidates cancel to maintain deterministic exposure
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

### Rebuild Market Structure
```bash
curl -X POST http://localhost:5050/api/market-structure/rebuild
```

### Rebuild Order Blocks
```bash
# Rebuilds market structure first, then order blocks
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
# Send a heartbeat tick to force broadcast
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
| ` websocket_clients: 0` | No dashboard connection | Refresh dashboard page |
| `pending_orders stuck at pending` | OB not touched or RR too low | Check `api/pending-orders/state` |
| `strategy enabled but no fills` | Paper engine not triggered | Check `api/state` for open position |
| `sqlite busy` | Concurrent write attempts | Back up DB, restart receiver |

## Version History

- **v1.2.1**: Dashboard price hotfix (XAUUSD Bid/Ask/Mid/Spread/Tick age)
- **v1.2**: Multi-bot runtime fan-out
- **v1.1**: Multi-bot router foundation
- **Final Build**: Paper-only execution, auto fill, replay preview
