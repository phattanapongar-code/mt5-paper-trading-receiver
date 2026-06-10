# MT5 Paper Trading Receiver v0.3

ฝั่ง Mac สำหรับรับ Tick จาก Windows MT5 Sender, สร้าง Candle M1/M5/M15/H1, คำนวณ MA/ATR และ import แท่ง M1 ย้อนหลังจาก MT5 เพื่อให้ MA300 พร้อมโดยไม่ต้องรอหลายวัน

## Mac: run receiver

```bash
cd ~/Documents/Hermess/mt5-paper-trading-receiver
source .venv/bin/activate
python run.py
```

## Mac: health and history status

```bash
curl http://localhost:5050/health
curl http://localhost:5050/api/history/status
curl http://localhost:5050/api/indicators/M15
```

## Windows: copy the history bootstrap script

คัดลอกไฟล์นี้ไปไว้ในโฟลเดอร์เดียวกับ `sender.py`:

```text
windows_addon/bootstrap_history.py
```

เปิด MT5, Login แล้วเปิด PowerShell ในโฟลเดอร์ sender:

```powershell
.\.venv\Scripts\Activate.ps1
python bootstrap_history.py --receiver http://172.20.10.4:5050 --symbol XAUUSD --count 10000
```

สคริปต์จะ:

1. ข้ามแท่ง M1 ปัจจุบันที่ยังไม่ปิด
2. อ่านแท่ง M1 ย้อนหลังจาก MT5
3. ตรวจ broker timestamp offset อัตโนมัติ เช่น `+10800s`
4. normalize เวลาให้ตรงกับ Candle สดฝั่ง Mac
5. ส่งข้อมูลเป็นชุดละ 1,000 แท่ง
6. ให้ Mac rebuild M5/M15/H1 และคำนวณ MA300

## What changed in v0.3

- ใช้ receiver arrival time สร้าง Candle สด และเก็บ `source_timestamp` ไว้ debug
- เพิ่ม migration คอลัมน์ `ticks.source_ts`
- เพิ่ม endpoint `POST /api/history/import/m1`
- เพิ่ม endpoint `GET /api/history/status`
- เพิ่ม rebuild M1 history → M5/M15/H1
- กัน aggregated candle ที่ไม่ครบแท่งรอบ session gap
- เพิ่ม `windows_addon/bootstrap_history.py`

ยังไม่เปิด auto strategy ใน patch นี้ รอบต่อไปจึงค่อยเพิ่ม Swing/BOS detector

## v0.4 Swing + BOS

เพิ่ม market structure detector จากแท่งปิดเท่านั้น:

```bash
curl -X POST http://localhost:5050/api/market-structure/rebuild
curl http://localhost:5050/api/market-structure/M15
curl "http://localhost:5050/api/swings/M15?limit=20"
curl "http://localhost:5050/api/bos/M15?limit=20"
```

BOS ใช้ candle close ข้าม confirmed swing; wick-only break จะไม่ถูกนับเป็น BOS
