# Install v0.3 Historical Bootstrap Patch

## 1. Mac: วางไฟล์ทับโปรเจกต์เดิม

คัดลอกทุกไฟล์ยกเว้นโฟลเดอร์ `windows_addon` ไปวางทับใน:

```text
~/Documents/Hermess/mt5-paper-trading-receiver
```

ถ้า Finder ถามเรื่องโฟลเดอร์ `app` หรือ `tests` ให้เลือก **ผสาน (Merge)**

## 2. Mac: restart receiver

```bash
cd ~/Documents/Hermess/mt5-paper-trading-receiver
source .venv/bin/activate
python run.py
```

## 3. Windows: เพิ่มสคริปต์ bootstrap

คัดลอก:

```text
windows_addon/bootstrap_history.py
```

ไปไว้ข้าง `sender.py` ใน Windows

เปิด PowerShell อีกหน้าต่าง โดยปล่อย `sender.py` เดิมทำงานต่อได้:

```powershell
cd "C:\Users\phatt\OneDrive\เดสก์ท็อป\vps\mt5_fetcher"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python bootstrap_history.py --receiver http://172.20.10.4:5050 --symbol XAUUSD --count 10000
```

## 4. Mac: verify

```bash
curl http://localhost:5050/api/history/status
curl http://localhost:5050/api/indicators/M15
curl http://localhost:5050/api/state
```
