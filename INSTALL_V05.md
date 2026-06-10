# Patch v0.5 — Strong Order Block Detector + Score

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

## Build Order Blocks from existing history

Run in a second Terminal tab:

```bash
curl -X POST http://localhost:5050/api/order-blocks/rebuild
```

## Inspect M15 candidates

```bash
curl "http://localhost:5050/api/order-blocks/M15?limit=20"
curl "http://localhost:5050/api/order-blocks/active/M15?limit=20"
curl http://localhost:5050/api/order-blocks/state/M15
curl http://localhost:5050/api/state
```

## Scope

v0.5 detects structural candidates only. The RR >= 1.5 gate, pending expiration after 8 candles, MA-structure cancellation, and paper execution are intentionally deferred to v0.6+.
