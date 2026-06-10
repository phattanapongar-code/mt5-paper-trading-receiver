# Final Build Installation

This patch upgrades v0.6 without deleting the existing SQLite database.

## Install on Mac

1. Stop `python run.py` with `Ctrl+C`.
2. Merge the ZIP contents into `~/Documents/Hermess/mt5-paper-trading-receiver`.
3. Run:

```bash
cd ~/Documents/Hermess/mt5-paper-trading-receiver
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

## Verify

```bash
curl http://localhost:5050/health
curl http://localhost:5050/api/state
curl http://localhost:5050/api/strategy/status
```

Open dashboard:

```text
http://localhost:5050/dashboard
```

## Enable paper-only automation intentionally

```bash
curl -X POST http://localhost:5050/api/strategy/enable
```

Disable:

```bash
curl -X POST http://localhost:5050/api/strategy/disable
```

No command is sent back to MT5. This build is paper trading only.

## Replay preview

```bash
curl -X POST http://localhost:5050/api/replay/run
curl http://localhost:5050/api/replay/latest
```

Replay is a research preview based on stored M1 OHLC bars. It is not tick-perfect and must not be treated as a production backtest.

## Backup SQLite

```bash
./scripts/backup_db.sh
```
