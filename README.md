# MT5 Multi-Bot Foundation v1.1

Patch แบบวางทับสำหรับอัปเกรด Receiver เดิม โดยไม่เขียนทับ logic ราคา, Candle, MA, BOS, OB, Pending Order หรือ Dashboard เดิม

## เพิ่มอะไร

- Profiles หลายชุด
- Bots หลายตัว
- Wallet แยกต่อ Bot
- Bot pending orders / positions / signal logs แยกต่อ Bot
- Compare API
- Multi-Bot Dashboard
- Migration อัตโนมัติจากระบบเดิม

## Migration อัตโนมัติ

เมื่อรัน installer ระบบจะ:

1. Backup `app/main.py`
2. Backup `data/receiver.sqlite3`
3. Inject Multi-Bot Router เข้า `app/main.py`
4. สร้าง Profile `default`
5. สร้าง Bot `trend-ob-baseline`
6. สร้าง Wallet ของ Baseline Bot โดยใช้ยอดเงินจาก `paper_account` เดิม
7. ผูก `trades` เดิมเข้ากับ Baseline Bot หากตารางเดิมมีอยู่
8. ย้าย `pending_orders` เดิมแบบ best-effort หาก schema รองรับ
9. ไม่ล้าง Tick, Candle, Swing, BOS และ OB เดิม

## ติดตั้งบน Mac

หยุด Receiver ก่อน จากนั้นแตก ZIP แล้ววางไฟล์ทับในโฟลเดอร์โปรเจกต์เดิม:

```bash
cd ~/Documents/Hermess/mt5-paper-trading-receiver
source .venv/bin/activate
python scripts/install_multibot_v11.py
python run.py
```

## ตรวจสอบ

```bash
curl http://localhost:5050/api/multibot/migration/status
curl http://localhost:5050/api/profiles
curl http://localhost:5050/api/bots
```

เปิด Dashboard ใหม่:

```text
http://localhost:5050/multi-bot-dashboard
```

Dashboard เดิมยังอยู่ตาม URL เดิม

## สร้าง Profile ทดลอง

```bash
curl -X POST http://localhost:5050/api/profiles \
  -H 'Content-Type: application/json' \
  -d '{"name":"experimental","description":"test variants"}'
```

## Clone Baseline Bot

```bash
curl -X POST http://localhost:5050/api/bots/1/clone \
  -H 'Content-Type: application/json' \
  -d '{"name":"trend-ob-strict"}'
```

## เปิดหรือปิด Bot

```bash
curl -X POST http://localhost:5050/api/bots/2/enable
curl -X POST http://localhost:5050/api/bots/2/disable
```

## Reset Wallet ของ Bot

```bash
curl -X POST http://localhost:5050/api/bots/2/wallet/reset \
  -H 'Content-Type: application/json' \
  -d '{"balance":500}'
```

## Compare Bots

```bash
curl 'http://localhost:5050/api/compare?bot_ids=1,2'
```

## หมายเหตุสำคัญ

v1.1 เป็น Multi-Bot Foundation: สร้างโครงสร้าง DB, API, Wallet และ Dashboard สำหรับหลาย Bot แล้ว แต่ runtime strategy เดิมยังคงทำงานเป็น Baseline Bot ตาม logic เดิม เพื่อไม่เสี่ยงทำลายระบบที่รันได้อยู่

ขั้นถัดไปคือ v1.2 Runtime Fan-Out: ส่ง market snapshot เดียวกันให้ Bot ที่เปิดใช้งานแต่ละตัว evaluate แยกกัน และสร้าง Pending/Position ลงตารางแยกของแต่ละ Bot
