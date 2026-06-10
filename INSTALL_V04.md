# Install v0.4 — Swing + BOS

วางไฟล์ทั้งหมดทับโปรเจกต์ Receiver บน Mac แล้วเลือก **Merge / ผสาน** เมื่อ Finder ถาม

```bash
cd ~/Documents/Hermess/mt5-paper-trading-receiver
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

ระบบจะสร้างตาราง SQLite ใหม่อัตโนมัติ ไม่ต้องลบฐานข้อมูลเดิม และไม่ต้องแก้ฝั่ง Windows

หากมี history จาก v0.3 อยู่แล้ว ให้ rebuild market structure หนึ่งครั้ง:

```bash
curl -X POST http://localhost:5050/api/market-structure/rebuild
```

ตรวจสอบ:

```bash
curl http://localhost:5050/api/market-structure/M15
curl "http://localhost:5050/api/swings/M15?limit=10"
curl "http://localhost:5050/api/bos/M15?limit=10"
```

## นิยาม v0.4

- ใช้แท่งที่ปิดแล้วเท่านั้น
- Swing ยืนยันเมื่อมีแท่งปิดด้านซ้ายและขวาครบ `SWING_WINDOW`
- BOS bullish: candle close ข้าม swing high
- BOS bearish: candle close ข้าม swing low
- wick แทงผ่านอย่างเดียวไม่นับเป็น BOS
- ค่า default `SWING_WINDOW=3`
