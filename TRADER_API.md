# MT5 Trade Execution Server — API Reference

**Host**: `http://100.71.60.113:5051`  
**Auth Header**: `X-API-Key: QrC7v9^HaUlW%l78tnhMPj7uZTWJSdSc`  
**Content-Type**: `application/json`

---

## 1. System

### GET /health

MT5 connection status + terminal info.

```bash
curl http://100.71.60.113:5051/health \
  -H "X-API-Key: QrC7v9^HaUlW%l78tnhMPj7uZTWJSdSc"
```

```json
{
  "ok": true,
  "connected": true,
  "terminal": "MetaTrader 5",
  "terminal_version": 6000,
  "account": {
    "login": 12345678,
    "balance": 10000.0,
    "equity": 10500.0,
    "margin": 500.0,
    "margin_free": 9500.0,
    "margin_level": 2100.0,
    "leverage": 100,
    "currency": "USD",
    "name": "Demo Account",
    "server": "ICMarkets-Demo"
  },
  "symbols": ["XAUUSD", "EURUSD", "GBPUSD"],
  "queue_size": 0,
  "error": null
}
```

---

### GET /trader/symbols

Symbol list ที่ sender กำลังส่งราคาอยู่ (อ่านจาก `symbols.json`)

```bash
curl http://100.71.60.113:5051/trader/symbols \
  -H "X-API-Key: QrC7v9^HaUlW%l78tnhMPj7uZTWJSdSc"
```

```json
{
  "symbols": ["XAUUSD", "EURUSD", "GBPUSD"]
}
```

---

### POST /trader/symbols

เปลี่ยน symbol list — เขียน `symbols.json` sender จะ auto-read ทุก loop

```bash
curl -X POST http://100.71.60.113:5051/trader/symbols \
  -H "X-API-Key: QrC7v9^HaUlW%l78tnhMPj7uZTWJSdSc" \
  -H "Content-Type: application/json" \
  -d '{"symbols":["XAUUSD","BTCUSD","EURUSD"]}'
```

```json
{
  "ok": true,
  "symbols": ["XAUUSD", "BTCUSD", "EURUSD"]
}
```

---

### GET /trader/symbols/available

Symbol ทั้งหมดที่ MT5 terminal มี + เทรดได้ (filter `trade_mode != disabled`)

```bash
curl http://100.71.60.113:5051/trader/symbols/available \
  -H "X-API-Key: QrC7v9^HaUlW%l78tnhMPj7uZTWJSdSc"
```

```json
{
  "success": true,
  "data": [
    {
      "symbol": "AUDCAD",
      "description": "Australian Dollar vs Canadian Dollar",
      "digits": 5,
      "volume_min": 0.01,
      "volume_max": 500,
      "volume_step": 0.01,
      "point": 1e-05,
      "contract_size": 100000
    },
    {
      "symbol": "XAUUSD",
      "description": "Gold vs US Dollar",
      "digits": 2,
      "volume_min": 0.01,
      "volume_max": 100,
      "volume_step": 0.01,
      "point": 0.01,
      "contract_size": 100
    }
  ],
  "count": 82
}
```

volume validation: ก่อนส่ง `/trade/open` ควร clamp `volume` ระหว่าง `volume_min`–`volume_max` และ round ตาม `volume_step`

---

## 2. Account

### GET /trade/account

Balance, equity, margin, leverage, etc.

```bash
curl http://100.71.60.113:5051/trade/account \
  -H "X-API-Key: QrC7v9^HaUlW%l78tnhMPj7uZTWJSdSc"
```

```json
{
  "ok": true,
  "login": 12345678,
  "balance": 10000.0,
  "equity": 10500.0,
  "margin": 500.0,
  "margin_free": 9500.0,
  "margin_level": 2100.0,
  "leverage": 100,
  "currency": "USD",
  "name": "Demo Account",
  "server": "ICMarkets-Demo",
  "trade_allowed": true,
  "trade_expert": true
}
```

---

### GET /trade/positions

Open positions ทั้งหมด (filter by `?symbol=XAUUSD` ได้)

```bash
curl http://100.71.60.113:5051/trade/positions \
  -H "X-API-Key: QrC7v9^HaUlW%l78tnhMPj7uZTWJSdSc"
```

```json
{
  "ok": true,
  "positions": [
    {
      "ticket": 12345678,
      "symbol": "XAUUSD",
      "type": "buy",
      "volume": 0.1,
      "open_price": 1920.5,
      "sl": 1900.0,
      "tp": 1950.0,
      "profit": 250.0,
      "commission": -3.5,
      "swap": -1.2,
      "open_time": 1718000000,
      "magic": 20240601,
      "comment": "trader"
    }
  ],
  "count": 1
}
```

---

## 3. Trading

### POST /trade/open — Market Order

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `symbol` | string | ✅ | e.g. `"XAUUSD"` |
| `type` | string | ✅ | `"buy"` or `"sell"` |
| `volume` | number | ✅ | Lot size (clamped to symbol min/max/step) |
| `sl` | number | ❌ | Stop Loss price |
| `tp` | number | ❌ | Take Profit price |
| `sl_pips` | number | ❌ | SL in pips from entry |
| `tp_pips` | number | ❌ | TP in pips from entry |
| `comment` | string | ❌ | Order comment |
| `magic` | number | ❌ | Magic number (default: `20240601`) |

```bash
curl -X POST http://100.71.60.113:5051/trade/open \
  -H "X-API-Key: QrC7v9^HaUlW%l78tnhMPj7uZTWJSdSc" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"XAUUSD","type":"buy","volume":0.1,"sl_pips":50,"tp_pips":100}'
```

```json
{
  "ok": true,
  "ticket": 12345678,
  "price": 1920.5,
  "volume": 0.1,
  "sl": 1915.5,
  "tp": 1930.5,
  "comment": ""
}
```

**SL/TP Priority**: `sl`/`tp` (price) > `sl_pips`/`tp_pips` > ไม่ส่ง = ไม่ตั้ง

---

### POST /trade/pending — Pending Order

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `symbol` | string | ✅ | e.g. `"XAUUSD"` |
| `type` | string | ✅ | `"buy_limit"`, `"sell_limit"`, `"buy_stop"`, `"sell_stop"` |
| `volume` | number | ✅ | Lot size |
| `price` | number | ✅ | Entry price |
| `sl` / `sl_pips` | number | ❌ | Stop Loss |
| `tp` / `tp_pips` | number | ❌ | Take Profit |
| `comment` | string | ❌ | |
| `magic` | number | ❌ | |
| `expiry_hours` | number | ❌ | Default: 24 |

```bash
curl -X POST http://100.71.60.113:5051/trade/pending \
  -H "X-API-Key: QrC7v9^HaUlW%l78tnhMPj7uZTWJSdSc" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"XAUUSD","type":"buy_limit","volume":0.1,"price":1900}'
```

```json
{
  "ok": true,
  "ticket": 12345679,
  "price": 1900.0,
  "volume": 0.1
}
```

**`type` format**: `<side>_<order_type>` — `buy_limit`, `sell_limit`, `buy_stop`, `sell_stop`

---

### POST /trade/close — Close by Ticket or Symbol

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ticket` | number | ❌ | Position ticket |
| `symbol` | string | ❌ | Symbol (close all positions of this symbol) |
| `comment` | string | ❌ | |

ต้องส่ง `ticket` หรือ `symbol` — อย่างน้อย 1 อย่าง

```bash
# Close by ticket
curl -X POST http://100.71.60.113:5051/trade/close \
  -H "X-API-Key: QrC7v9^HaUlW%l78tnhMPj7uZTWJSdSc" \
  -H "Content-Type: application/json" \
  -d '{"ticket":12345678}'

# Close all positions of a symbol
curl -X POST http://100.71.60.113:5051/trade/close \
  -H "X-API-Key: QrC7v9^HaUlW%l78tnhMPj7uZTWJSdSc" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"XAUUSD"}'
```

```json
{
  "ok": true,
  "ticket": 12345678,
  "price": 1925.0,
  "volume": 0.1
}
```

---

### POST /trade/close_all — Close All Positions

```bash
curl -X POST http://100.71.60.113:5051/trade/close_all \
  -H "X-API-Key: QrC7v9^HaUlW%l78tnhMPj7uZTWJSdSc"
```

```json
{
  "ok": true,
  "results": [
    {"ok": true, "ticket": 12345678, "price": 1925.0, "volume": 0.1}
  ]
}
```

---

### POST /trade/modify — Modify SL/TP

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ticket` | number | ✅ | Position ticket |
| `sl` | number | ❌ | New SL price |
| `tp` | number | ❌ | New TP price |
| `sl_pips` | number | ❌ | SL in pips from entry |
| `tp_pips` | number | ❌ | TP in pips from entry |

```bash
curl -X POST http://100.71.60.113:5051/trade/modify \
  -H "X-API-Key: QrC7v9^HaUlW%l78tnhMPj7uZTWJSdSc" \
  -H "Content-Type: application/json" \
  -d '{"ticket":12345678,"sl":1900,"tp":1960}'
```

```json
{
  "ok": true,
  "ticket": 12345678,
  "sl": 1900.0,
  "tp": 1960.0
}
```

---

## 4. Webhook (trader.py → Receiver)

After every trade action, trader.py POSTs to `http://100.95.147.98:5050/trader/webhook`

### Event: `order_filled`

```json
{
  "event": "order_filled",
  "ticket": 12345678,
  "symbol": "XAUUSD",
  "type": "buy",
  "volume": 0.1,
  "open_price": 1920.5,
  "sl": 1900.0,
  "tp": 1950.0,
  "commission": -3.5
}
```

### Event: `order_pending`

```json
{
  "event": "order_pending",
  "ticket": 12345679,
  "symbol": "XAUUSD",
  "type": "buy_limit",
  "volume": 0.1,
  "price": 1900.0
}
```

### Event: `position_closed`

```json
{
  "event": "position_closed",
  "ticket": 12345678,
  "symbol": "XAUUSD",
  "type": "buy",
  "volume": 0.1,
  "close_price": 1925.0,
  "profit": 45.0,
  "commission": -3.5
}
```

### Event: `position_modified`

```json
{
  "event": "position_modified",
  "ticket": 12345678,
  "symbol": "XAUUSD",
  "sl": 1900.0,
  "tp": 1960.0
}
```

### Event: `all_positions_closed`

```json
{
  "event": "all_positions_closed",
  "count": 3
}
```

---

## 5. Error Handling

Response format เมื่อ error:

```json
{
  "ok": false,
  "error": "Not enough money",
  "error_code": 134
}
```

### Common MT5 Error Codes

| Code | Message | Meaning |
|------|---------|---------|
| 10004 | Trade is disabled | Symbol trading ปิดอยู่ |
| 10006 | No connection | MT5 terminal disconnected |
| 10007 | Too frequent requests | ส่ง request ถี่เกิน |
| 10010 | Invalid volume | Lot size ผิด (check min/max/step) |
| 10011 | Invalid price | ราคาไม่ถูกต้อง |
| 10012 | Invalid stops | SL/TP ผิด (too close to market) |
| 10014 | Not enough money | Margin ไม่พอ |
| 10016 | Market is closed | ตลาดปิด (weekend/holiday) |
| 10019 | Buy/Sell limit exceeded | เกิน limit |
| 130 | Invalid stops | SL/TP ผิด format |
| 134 | Not enough money | Balance ไม่พอ |
| 138 | Requote | ราคาเปลี่ยนไปแล้ว |
| 4014 | Symbol not found | Symbol ไม่มีใน MT5 |

---

## 6. Rate Limiting

- Max **5 requests/second** per IP
- ถ้าเกิน → `429 Too Many Requests`:
  ```json
  {
    "ok": false,
    "error": "Rate limit exceeded. Try again shortly."
  }
  ```

---

## 7. Notes

| Topic | Detail |
|-------|--------|
| **Host** | `100.71.60.113:5051` (Tailscale) |
| **API Key** | `QrC7v9^HaUlW%l78tnhMPj7uZTWJSdSc` |
| **IP Whitelist** | Receiver IP: `100.95.147.98` |
| **Field name** | ใช้ `volume` (ไม่ใช่ `lot`) |
| **SL/TP Priority** | `sl`/`tp` (price) > `sl_pips`/`tp_pips` |
| **Pending type** | `"buy_limit"`, `"sell_limit"`, `"buy_stop"`, `"sell_stop"` |
| **Connectivity** | ผ่าน Tailscale ทั้งคู่ |
