# Plan v2.5.0 — Backtest Engine + RSI Strategy + Telegram Alerts + Trailing Stop

## Overview

Add 4 major features:

1. **Trailing Stop** — SL ขยับตาม price อัตโนมัติ
2. **Telegram Alerts** — แจ้งเตือนเมื่อ TP/SL/Error
3. **RSI + MACD + Bollinger Bands** — Indicators เพิ่ม + 3 strategies ใหม่
4. **Backtest Engine** — Real tick simulation + Parameter optimizer

---

## 1. Backtest Engine

### Concept
ใช้ M1 closed candles + `tick_count` เพื่อ regenerate ticks แบบ volume-weighted แล้วป้อนเข้า pipeline เดียวกับ `/price` endpoint ทุกประการ — candle engine, market structure, OB detection, bot evaluation ครบทุกขั้นตอน

### New Files

#### `app/backtest/__init__.py`
- Empty (package marker)

#### `app/backtest/models.py`
```python
from pydantic import BaseModel
from typing import Literal, Optional

class BacktestRequest(BaseModel):
    bot_id: Optional[int] = None
    strategy_type: str = "trend_ob"
    parameters: dict = {}
    symbol: str = "XAUUSD"
    timeframe: str = "M15"
    start_time: int
    end_time: int
    initial_balance: float = 10000.0

class OptimizeRequest(BaseModel):
    strategy_type: str
    param_ranges: dict  # {param_name: [val1, val2, ...]}
    symbol: str = "XAUUSD"
    timeframe: str = "M15"
    start_time: int
    end_time: int
    initial_balance: float = 10000.0
    optimization_metric: str = "sharpe_ratio"
```

#### `app/backtest/engine.py`

**คลาสหลัก `BacktestEngine`:**

```python
class BacktestEngine:
    def __init__(self, config: BacktestRequest):
        self.config = config
        self.trades: list[dict] = []
        self.equity_curve: list[dict] = []  # [{time, equity}]
        self.balance = config.initial_balance
        self.position: dict | None = None
        self.pending: dict | None = None

    def run(self) -> dict:
```

**Pipeline:**

```
1. LOAD closed M1 candles FROM candles WHERE symbol=? AND timeframe='M1' 
   AND is_closed=1 AND open_time BETWEEN ? AND ? ORDER BY open_time

2. INIT in-memory engines (reset every run):
   - CandleEngine() — rebuild from scratch
   - MarketStructureEngine() — new instance
   - OrderBlockEngine() — new instance

3. WALK each M1 candle:
   a) simulate_ticks(candle) → list of {bid, ask, ts}
   b) For each tick:
      - candle_engine.update_tick(symbol, bid, ask, ts)
      - if closed timeframes → structure.refresh() + order_blocks.refresh()
      - evaluate_bot(tick) — same _evaluate_bot logic from runtime.py

4. CLOSE any remaining open position at end_time
```

**Tick simulation — `simulate_ticks(candle)`:**
```python
def simulate_ticks(candle: dict) -> list[dict]:
    num_ticks = candle.get("tick_count") or 60
    o, c, h, l = candle["open"], candle["close"], candle["high"], candle["low"]
    ticks = []
    for i in range(num_ticks):
        progress = (i + 1) / num_ticks
        base = o + (c - o) * progress
        noise = random.uniform(l - base, h - base) * 0.3
        price = max(l, min(h, base + noise))
        spread = random.uniform(0.3, 0.8)
        mid = price
        ts = candle["open_time"] + (candle["close_time"] - candle["open_time"]) * progress
        ticks.append({
            "type": "tick",
            "symbol": candle["symbol"],
            "bid": round(mid - spread / 2, 2),
            "ask": round(mid + spread / 2, 2),
            "timestamp": int(ts),
            "seq": i,
        })
    return ticks
```

**Evaluate bot logic:**
ใช้ helper functions จาก `runtime.py` โดยตรง:
- `_close_position()` logic → in-memory balance update
- `_round_lot()` → lot sizing
- **ไม่ใช้ DB จริง** — ใช้ in-memory dict แทน `bot_positions`

#### `app/backtest/report.py`
```python
def generate_report(trades, equity_curve, initial_balance) -> dict:
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    
    return {
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins)/len(trades), 4) if trades else 0,
        "net_pnl": round(sum(t["pnl"] for t in trades), 2),
        "gross_profit": round(sum(t["pnl"] for t in wins), 2),
        "gross_loss": round(abs(sum(t["pnl"] for t in losses)), 2),
        "profit_factor": round(gross_profit/gross_loss, 2) if gross_loss else None,
        "sharpe_ratio": round(sharpe_ratio(trades), 2),
        "max_drawdown_pct": round(max_drawdown(equity_curve) * 100, 2),
        "avg_r": round(mean([t.get("r_multiple", 0) for t in trades]), 2),
        "total_r": round(sum(t.get("r_multiple", 0) for t in trades), 2),
        "final_balance": round(equity_curve[-1]["equity"], 2),
        "return_pct": round((final - initial) / initial * 100, 2),
        "equity_curve": equity_curve,
        "trades": trades[-100:],
    }
```

#### `app/backtest/optimizer.py`
```python
class ParameterOptimizer:
    def run(self) -> list[dict]:
        # Grid search over all param combinations
        param_names = list(self.config.param_ranges.keys())
        param_values = list(self.config.param_ranges.values())
        combinations = list(product(*param_values))
        results = []
        for combo in combinations:
            params = dict(zip(param_names, combo))
            bt = BacktestEngine(BacktestRequest(
                strategy_type=self.config.strategy_type,
                parameters=params, symbol=self.config.symbol,
                timeframe=self.config.timeframe,
                start_time=self.config.start_time, end_time=self.config.end_time,
                initial_balance=self.config.initial_balance,
            ))
            report = bt.run()
            results.append({**params, **{k: report[k] for k in [
                "total_trades","win_rate","net_pnl","profit_factor",
                "sharpe_ratio","max_drawdown_pct","avg_r","total_r"
            ]}})
        results.sort(key=lambda r: r.get(self.config.optimization_metric, 0), reverse=True)
        return results
```

---

## 2. RSI + MACD + BB Indicators + Strategies

### `app/indicators.py` — ฟังก์ชันเพิ่ม

```python
def macd(closes: list[float], fast=12, slow=26, signal=9) -> dict:
    """MACD line, Signal line, Histogram"""
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = ema(macd_line, signal)
    histogram = [m - s for m, s in zip(macd_line, signal_line)]
    return {
        "macd": macd_line[-1] if macd_line else None,
        "macd_signal": signal_line[-1] if signal_line else None,
        "macd_histogram": histogram[-1] if histogram else None,
    }

def bollinger_bands(closes: list[float], period=20, std_dev=2) -> dict:
    """Upper, Middle (SMA), Lower bands"""
    if len(closes) < period:
        return {"bb_upper": None, "bb_middle": None, "bb_lower": None}
    sma_val = sma(closes, period)
    window = closes[-period:]
    variance = sum((x - sma_val) ** 2 for x in window) / period
    std = math.sqrt(variance)
    return {
        "bb_upper": sma_val + std_dev * std,
        "bb_middle": sma_val,
        "bb_lower": sma_val - std_dev * std,
    }

def ema(values: list[float], period: int) -> list[float]:
    """Exponential Moving Average"""
    if len(values) < period:
        return []
    multiplier = 2 / (period + 1)
    result = [sum(values[:period]) / period]  # seed SMA
    for v in values[period:]:
        result.append((v - result[-1]) * multiplier + result[-1])
    return result
```

แก้ `compute_indicators()` — return fields เพิ่ม: `rsi14`, `macd`, `macd_signal`, `macd_histogram`, `bb_upper`, `bb_middle`, `bb_lower`

### Strategies ใหม่ (3 ไฟล์)

#### `app/multibot/strategies/rsi_meanrev.py` (ปรับปรุงใหม่)
```python
def decide(conn, bot, tick, params, now) -> dict | None:
    candles = get_closed_candles(conn, bot["symbol"], bot["timeframe"], 100)
    ind = compute_indicators(candles)
    rsi = ind["rsi14"]
    if rsi is None: return None
    trend = ind["trend"]
    use_trend_filter = params.get("rsi_trend_filter", True)
    oversold = params.get("rsi_oversold", 30)
    overbought = params.get("rsi_overbought", 70)
    if rsi < oversold:
        if use_trend_filter and trend != "BULLISH": return None
        ob = find_nearest_ob(conn, bot["symbol"], bot["timeframe"], "buy")
        if not ob: return None
        return build_decision("buy", ob, tick, params, now)
    if rsi > overbought:
        if use_trend_filter and trend != "BEARISH": return None
        ob = find_nearest_ob(conn, bot["symbol"], bot["timeframe"], "sell")
        if not ob: return None
        return build_decision("sell", ob, tick, params, now)
    return None
```

#### `app/multibot/strategies/macd_cross.py` (ใหม่)
- BUY: MACD line crosses ABOVE Signal line
- SELL: MACD line crosses BELOW Signal line
- ใช้ crossover detection (current MACD > signal AND previous MACD <= signal)

#### `app/multibot/strategies/bb_breakout.py` (ใหม่)
- BUY: Close > BB upper (momentum breakout)
- SELL: Close < BB lower

### Frontend: Charts.tsx multi-pane

เพิ่ม toggle buttons: `[RSI] [MACD] [BB]`
- RSI: secondary pane (line chart + 30/70 lines)
- MACD: secondary pane (MACD line + signal line + histogram)
- BB: overlay on main chart (upper/middle/lower bands)

lightweight-charts APIs:
- `chart.addPane()` → get pane ID
- `chart.addSeries(LineSeries, { pane: paneId, ... })`
- `chart.addSeries(HistogramSeries, { pane: paneId, ... })`

---

## 3. Telegram Alert System

### `app/alert.py` (ใหม่)

```python
import aiohttp
import asyncio
import logging

logger = logging.getLogger(__name__)

class AlertEngine:
    def __init__(self):
        self.bot_token: str | None = None
        self.chat_id: str | None = None
        self.enabled: bool = False
        self._session: aiohttp.ClientSession | None = None

    def configure(self, bot_token: str, chat_id: str, enabled: bool = True):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled

    async def send(self, message: str) -> bool:
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False
        try:
            if not self._session:
                self._session = aiohttp.ClientSession()
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            async with self._session.post(url, json={
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
            }) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def notify_trade_open(self, bot_name, side, entry, sl, tp, lot, symbol):
        msg = f"{'🟢' if side=='buy' else '🔴'} <b>Trade Opened</b>\nBot: {bot_name}\nSymbol: {symbol}\nSide: {side.upper()}\nEntry: {entry}\nSL: {sl}\nTP: {tp}\nLot: {lot}"
        asyncio.ensure_future(self.send(msg))

    def notify_trade_close(self, bot_name, side, pnl, reason, symbol, r=0):
        msg = f"{'✅' if pnl>0 else '❌'} <b>Trade Closed</b>\nBot: {bot_name}\nSymbol: {symbol}\nPnL: {pnl:+.2f}\nR: {r:+.2f}\nReason: {reason}"
        asyncio.ensure_future(self.send(msg))

    def notify_error(self, bot_name, error):
        asyncio.ensure_future(self.send(f"🚨 <b>Bot Error</b>\nBot: {bot_name}\nError: {error}"))

    async def test(self) -> bool:
        return await self.send("✅ <b>Alert System Test</b>\nYour MT5 Paper Trading alerts are working!")

alert_engine = AlertEngine()  # singleton
```

### Integration points

| จุด | ไฟล์ | แก้ไข |
|-----|------|-------|
| Trade opened | `runtime.py` — after pending order fills | `alert_engine.notify_trade_open(...)` |
| Trade closed | `runtime.py` — _close_position() | `alert_engine.notify_trade_close(...)` |
| Bot error | `runtime.py` — except block of SAVEPOINT | `alert_engine.notify_error(...)` |

### Storage
ใช้ `multibot_runtime_settings` key-value ที่มีอยู่:
```
alert.bot_token = "123456:ABC..."
alert.chat_id = "-100123456789"
alert.enabled = "1"
```

### Frontend: Settings.tsx

เพิ่ม section:
- Text input "Telegram Bot Token" (type=password)
- Text input "Chat ID"
- Toggle "Enable Alerts"
- Button "Test Alert" → POST `/api/alerts/test`

---

## 4. Trailing Stop

### Logic (ใน `runtime.py` _evaluate_bot)

หลังจาก check SL/TP (บรรทัดเดิมที่ bid<=sl หรือ ask>=sl) และก่อน `return`:

```python
if position and bot_params.get("trailing_enabled"):
    activate_pips = bot_params.get("trail_activation_pips", 10)
    trail_dist = bot_params.get("trail_distance_pips", 5)
    step_pips = bot_params.get("trail_step_pips", 1)
    
    pip_value = _pip_value(symbol)  # 0.01 for JPY, 0.0001 for others, 0.1 for XAU
    price_diff = (bid - position["entry"]) if position["side"]=="buy" else (position["entry"] - ask)
    
    if price_diff >= activate_pips * pip_value:
        if position["side"] == "buy":
            new_sl = bid - trail_dist * pip_value
            old_sl = position["stop_loss"]
            if new_sl > old_sl + step_pips * pip_value:
                conn.execute("UPDATE bot_positions SET stop_loss=?, updated_at=? WHERE id=?", 
                           (new_sl, now, position["id"]))
                position["stop_loss"] = new_sl  # update local copy
        else:  # sell
            new_sl = ask + trail_dist * pip_value
            old_sl = position["stop_loss"]
            if new_sl < old_sl - step_pips * pip_value:
                conn.execute("UPDATE bot_positions SET stop_loss=?, updated_at=? WHERE id=?",
                           (new_sl, now, position["id"]))
                position["stop_loss"] = new_sl
```

### Parameters (per-bot, เพิ่มใน `default_parameters()`)
```python
"trailing_enabled": False,
"trail_activation_pips": 10,   # ต้องได้กำไรเท่าไหร่ก่อนถึง activate
"trail_distance_pips": 5,      # SL จะห่างจาก price เท่าไหร่
"trail_step_pips": 1,          # ขยับ SL ทุกกี่ pip
```

### Frontend: BotDetail.tsx + Charts.tsx

**BotDetail.tsx** — Params tab มี input fields:
- "Enable Trailing Stop" toggle
- "Activation (pips)" number
- "Distance (pips)" number
- "Step (pips)" number

**Charts.tsx** — ถ้า position เปิดอยู่และมี trailing SL:
- แสดง dotted line ที่ trailing SL level (สีม่วง แตกต่างจาก SL ปกติ)
- อัปเดตทุก 5s

---

## 5. Database Migrations

```sql
-- ตารางใหม่ใน app/storage.py
CREATE TABLE IF NOT EXISTS backtest_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bot_id INTEGER,
  strategy_type TEXT NOT NULL,
  symbol TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  parameters_json TEXT NOT NULL DEFAULT '{}',
  start_time INTEGER NOT NULL,
  end_time INTEGER NOT NULL,
  config_json TEXT NOT NULL DEFAULT '{}',
  total_trades INTEGER DEFAULT 0,
  wins INTEGER DEFAULT 0,
  losses INTEGER DEFAULT 0,
  win_rate REAL DEFAULT 0,
  net_pnl REAL DEFAULT 0,
  gross_profit REAL DEFAULT 0,
  gross_loss REAL DEFAULT 0,
  profit_factor REAL DEFAULT 0,
  sharpe_ratio REAL DEFAULT 0,
  max_drawdown_pct REAL DEFAULT 0,
  avg_r REAL DEFAULT 0,
  total_r REAL DEFAULT 0,
  final_balance REAL DEFAULT 0,
  return_pct REAL DEFAULT 0,
  equity_curve_json TEXT DEFAULT '[]',
  trades_json TEXT DEFAULT '[]',
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS backtest_optimize_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  strategy_type TEXT NOT NULL,
  param_ranges_json TEXT NOT NULL,
  symbol TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  start_time INTEGER NOT NULL,
  end_time INTEGER NOT NULL,
  optimization_metric TEXT NOT NULL DEFAULT 'sharpe_ratio',
  total_combinations INTEGER DEFAULT 0,
  results_json TEXT DEFAULT '[]',
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);
```

Migration version: `app/multibot/db.py` bump `SCHEMA_VERSION = "1.3"`

---

## 6. API Endpoints สรุป

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/backtest/run` | Run backtest |
| POST | `/api/backtest/optimize` | Parameter optimization |
| GET | `/api/backtest/history` | Past backtest runs |
| GET | `/api/backtest/runs/{id}` | Full backtest result |
| POST | `/api/backtest/clone-bot/{run_id}` | Clone best params → bot |
| POST | `/api/alerts/test` | Test Telegram alert |
| GET | `/api/alerts/config` | Get alert config |
| POST | `/api/alerts/config` | Save alert config |
| GET | `/api/indicators/{tf}` | ← return fields เพิ่ม (rsi14, macd, bb) |

---

## 7. Frontend Pages

### 7a. `/backtest` — หน้าใหม่ `Backtest.tsx`

**State:**
- `mode: 'bot' | 'custom'`
- `selectedBotId: number | null`
- `strategyType: string`
- `parameters: string` (JSON)
- `symbol, timeframe, startDate, endDate`
- `initialBalance: number`
- `running: boolean`
- `result: BacktestResult | null`

**Component tree:**
```
Backtest
├── ConfigSection
│   ├── ModeToggle (bot / custom)
│   ├── BotSelector (dropdown)
│   ├── StrategySelector
│   ├── ParameterEditor (JSON textarea or form)
│   ├── SymbolSelector (reuse from Layout)
│   ├── TimeframeSelector
│   ├── DateRangePicker (start + end date inputs)
│   ├── InitialBalanceInput
│   └── RunButton (POST /api/backtest/run)
└── ResultSection (shown after run)
    ├── SummaryCards (8 metric cards)
    ├── EquityCurveChart (lightweight-charts line)
    ├── DrawdownChart (lightweight-charts area, red)
    ├── TradeListTable
    ├── PnLCalendar (reuse PnlCalendar component)
    ├── ExportCSVButton
    └── CloneToBotButton
```

### 7b. `/backtest/optimize` — หน้าใหม่ `BacktestOptimize.tsx`

**State:**
- `strategyType: string`
- `paramRanges: Record<string, {min, max, step}>`
- `symbol, timeframe, startDate, endDate`
- `optimizationMetric: string`
- `running: boolean, progress: {done, total}`
- `results: OptimizeResult[]`

**Component tree:**
```
BacktestOptimize
├── ConfigSection
│   ├── StrategySelector
│   ├── ParameterRangeEditor (dynamic: one row per param)
│   │   └── for each param: [name] [min] [max] [step]
│   ├── Symbol/Timeframe/Date (same as backtest)
│   ├── MetricSelector (Sharpe/ProfitFactor/NetPnL/TotalR)
│   └── OptimizeButton (POST /api/backtest/optimize)
└── ResultsSection
    ├── ProgressBar (while running)
    ├── ResultsTable (sortable by metric)
    │   └── Click row → navigate to backtest detail with those params
    └── BestParamsSummary (highlight top row)
```

### 7c. Charts.tsx — Toggle panes

เพิ่ม toggle buttons หลัง timeframe selector:
```tsx
{[{key:'rsi',label:'RSI'},{key:'macd',label:'MACD'},{key:'bb',label:'BB'}].map(t => (
  <button key={t.key}
    onClick={() => toggleIndicator(t.key)}
    className={`px-2 py-1 text-xs rounded border cursor-pointer ${
      visibleIndicators[t.key] ? 'bg-primary/10 text-primary border-primary/50' : 'bg-surface-card-dark text-muted border-hairline-on-dark'
    }`}
  >{t.label}</button>
))}
```

Pane management:
```tsx
const [visibleIndicators, setVisibleIndicators] = useState({rsi: false, macd: false, bb: false})
const paneRefs = useRef<{rsi?: number; macd?: number}>({})

useEffect(() => {
  if (visibleIndicators.rsi && paneRefs.current.rsi === undefined) {
    paneRefs.current.rsi = chart.addPane()
    rsiSeriesRef.current = chart.addSeries(LineSeries, {
      pane: paneRefs.current.rsi,
      color: '#8c6cd8', lineWidth: 1, title: 'RSI(14)',
    })
    // add 30/70 lines
  }
  // MACD similar
  if (visibleIndicators.bb) {
    // Bollinger bands on main chart (no new pane needed)
  }
  // Resize chart height based on visible panes
  chart.applyOptions({ height: 500 + (visibleIndicators.rsi || visibleIndicators.macd ? 120 : 0) })
}, [visibleIndicators, indicators])
```

### 7d. Settings.tsx — Telegram config section

```
── Telegram Alerts ───────────────────
  Bot Token: [••••••••••••••••••••]  (password input)
  Chat ID:   [ -100123456789      ]
  Enabled:   [✓]                    (toggle)
  [Test Alert]                      (button → POST /api/alerts/test → toast)
```

---

## 8. Timeline & Dependencies

```
Day 1-2:   Alert System (Telegram)
              app/alert.py (new), config, Settings UI
              
Day 1-2:   Trailing Stop
              runtime.py (SL update), BotDetail.tsx, Charts.tsx
              ★ Can run parallel with Alert System
              
Day 2-4:   RSI + MACD + BB Indicators
              indicators.py (add functions), Charts.tsx (multi-pane)
              Strategies: rsi_meanrev, macd_cross, bb_breakout
              
Day 5-8:   Backtest Engine
              app/backtest/* (6 ไฟล์ใหม่)
              Depends on: indicators.py + all strategies ready
              
Day 8-10:  Frontend pages (Backtest, Optimize)
              Backtest.tsx, BacktestOptimize.tsx
              Depends on: backtest engine complete
```

---

## 9. File Change Summary

### New files (10)
| File | Lines (est) |
|------|------------|
| `app/backtest/__init__.py` | 1 |
| `app/backtest/models.py` | 30 |
| `app/backtest/engine.py` | 250 |
| `app/backtest/report.py` | 80 |
| `app/backtest/optimizer.py` | 60 |
| `app/backtest/router.py` | 50 |
| `app/alert.py` | 100 |
| `app/multibot/strategies/macd_cross.py` | 50 |
| `app/multibot/strategies/bb_breakout.py` | 50 |
| `frontend/src/pages/Backtest.tsx` | 300 |
| `frontend/src/pages/BacktestOptimize.tsx` | 250 |

### Modified files (14)
| File | Changes |
|------|---------|
| `app/indicators.py` | +macd(), +bollinger_bands(), +ema(), update compute_indicators() |
| `app/main.py` | Register backtest router, alert endpoints, update indicators endpoint |
| `app/storage.py` | Add backtest tables to init_db() |
| `app/multibot/db.py` | Bump to v1.3, add default params |
| `app/multibot/runtime.py` | Trailing SL logic, alert integration |
| `app/multibot/strategies/__init__.py` | Register macd_cross, bb_breakout |
| `app/multibot/strategies/rsi_meanrev.py` | Rewrite with trend filter |
| `frontend/src/App.tsx` | +Routes for /backtest, /backtest/optimize |
| `frontend/src/components/Layout.tsx` | +Nav links |
| `frontend/src/pages/Charts.tsx` | +RSI/MACD/BB panes toggle |
| `frontend/src/pages/Settings.tsx` | +Telegram config form |
| `frontend/src/pages/BotDetail.tsx` | +Backtest button, trailing config |
| `frontend/src/pages/BotManager.tsx` | Show all 5 strategies |
| `frontend/src/components/EquityChart.tsx` | Reuse for backtest equity curve |
