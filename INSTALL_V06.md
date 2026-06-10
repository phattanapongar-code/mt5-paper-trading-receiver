# Patch v0.6 — Pending Orders + Expiration + RR Gate

## Install on Mac

1. Stop receiver with `Ctrl+C`.
2. Copy this patch over the existing project and choose **Merge** when Finder asks.
3. Start the receiver:

```bash
cd ~/Documents/Hermess/mt5-paper-trading-receiver
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

## Rebuild structural state from existing history

```bash
curl -X POST http://localhost:5050/api/order-blocks/rebuild
```

## Inspect pending-order staging

```bash
curl http://localhost:5050/api/pending-orders/state
curl "http://localhost:5050/api/pending-orders?limit=20"
curl "http://localhost:5050/api/pending-orders/rejections?limit=20"
curl -X POST http://localhost:5050/api/pending-orders/evaluate
curl http://localhost:5050/api/state
```

## Rules in v0.6

- Only M15 Strong OB candidates are eligible.
- Trend must align: bullish OB + BULLISH trend or bearish OB + BEARISH trend.
- Live bid/ask must touch the OB zone before a pending order is staged.
- Entry is the OB midpoint.
- SL is beyond OB structure with a 30% OB-range buffer.
- TP defaults to 2R and RR must be >= 1.5.
- Only one active pending order is allowed.
- Pending order cancels after 8 M15 candles, when MA structure changes, when OB invalidates, or when spread becomes excessive.
- Repeated rejection logs are rate-limited to avoid database growth during fast Tick streams.
- Auto paper fill is intentionally deferred to v0.7.
