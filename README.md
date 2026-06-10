# MT5 Paper Trading Receiver v0.2

ฝั่ง Mac สำหรับรับราคา Tick จาก Windows MT5 Sender แล้วรวม Tick เป็น Candle M1/M5/M15/H1 พร้อม MA/ATR และ Paper Trading เบื้องต้น

## Run on Mac

```bash
cd ~/Documents/Hermess/mt5-paper-trading-receiver
source .venv/bin/activate
python run.py
```

ถ้ายังไม่ได้ติดตั้ง dependencies:

```bash
python -m pip install -r requirements.txt
```

## Health

```bash
curl http://localhost:5050/health
```

## State

```bash
curl http://localhost:5050/api/state
```

## Candles

```bash
curl http://localhost:5050/api/candles/M15?limit=20
curl http://localhost:5050/api/candles/M15?limit=20\&closed_only=true
```

## Indicators

```bash
curl http://localhost:5050/api/indicators/M15
```

## Paper Trade Manual

```bash
curl -X POST http://localhost:5050/api/paper/open \
  -H 'Content-Type: application/json' \
  -d '{"side":"buy","lot":0.01,"stop_loss":3300,"take_profit":3400,"note":"manual_test"}'
```

```bash
curl -X POST http://localhost:5050/api/paper/close \
  -H 'Content-Type: application/json' \
  -d '{"note":"manual_close"}'
```

## What changed in v0.2

- เพิ่ม Candle Aggregator: M1/M5/M15/H1
- เก็บ candles ลง SQLite
- เพิ่ม MA60/MA80/MA300
- เพิ่ม ATR14 และ Average Body 20
- เพิ่ม Trend Context: BULLISH / BEARISH / NEUTRAL / WARMING_UP
- เพิ่ม endpoint `/api/candles/{timeframe}`
- เพิ่ม endpoint `/api/indicators/{timeframe}`
- `/api/state` แสดง indicator ทุก timeframe

ยังไม่เปิด strategy อัตโนมัติใน patch นี้ เพื่อให้ตรวจ Candle/MA ให้ถูกก่อน
