# MT5 Paper Trading Receiver — Final Paper Build

Final paper-only build for receiving XAUUSD ticks from a Windows MT5 sender and evaluating the M15 trend-following Strong Order Block strategy on macOS.

## Included pipeline

```text
Windows MT5 sender
→ Mac tick receiver
→ M1/M5/M15/H1 candles
→ MA60/MA80/MA300 + ATR14
→ swing points + BOS
→ Strong OB scoring
→ M15 pending orders with 8-candle expiry
→ optional auto paper fill
→ SL/TP close + PnL + R multiple
→ dashboard + stats + replay preview
```

## Safety boundary

This build is **paper-only**. It never sends orders back to MT5. Auto paper execution is installed but OFF by default.

## Run

```bash
cd ~/Documents/Hermess/mt5-paper-trading-receiver
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

Dashboard: `http://localhost:5050/dashboard`

Enable auto paper only when ready:

```bash
curl -X POST http://localhost:5050/api/strategy/enable
```

Disable:

```bash
curl -X POST http://localhost:5050/api/strategy/disable
```

## Key endpoints

```text
GET  /health
GET  /api/state
GET  /api/stats
GET  /api/trades
GET  /api/pending-orders/state
POST /api/order-blocks/rebuild
POST /api/replay/run
GET  /api/replay/latest
GET  /dashboard
```

## Replay caveat

Replay is a research preview based on stored M1 OHLC bars. It is conservative when both SL and TP occur inside one M1 bar, but it is not a tick-perfect broker backtest.
