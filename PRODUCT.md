# Product

## Register

product

## Users

Trader / ผู้ใช้ที่ต้องการจัดการ MT5 paper trading system ผ่าน dashboard
- ใช้ตอนกำลัง monitor การเทรดแบบ real-time
- ต้องการเห็นข้อมูล ticks, candles, indicators แบบ live
- จัดการ multi-bot system (profiles, bots, wallets)
- วิเคราะห์ performance (PnL, win rate, equity curve)
- ดู market structure (swing points, BOS, order blocks)
- จัดการ pending orders

## Product Purpose

Dashboard สำหรับควบคุมและ monitor MT5 paper trading receiver
- ดู live tick, candles, indicators แบบ real-time
- จัดการ multi-bot system: profiles, bots, wallets
- ดู trade history พร้อม analytics
- ดู market structure visualization
- ควบคุม auto execution on/off
- real-time updates ผ่าน WebSocket

## Brand Personality

3 words: **edgy, precise, immersive**

Dark cyberpunk aesthetic ให้ความรู้สึกเหมือน trading control room
- มืดเป็นพื้น, accent สีสด (cyan, neon green, magenta) สำหรับ highlight ข้อมูลสำคัญ
- มืออาชีพ, เทคสูง, ดูจริงจัง
- ให้ความสำคัญกับ performance และความเร็ว

## Anti-references

- ❌ MT5 desktop UI (รก, เมนูเยอะเกิน, ดู outdated)
- ❌ admin template ทั่วไปที่สีเทาจืดๆ
- ❌ UX ที่ซับซ้อนหรือมี unnecessary steps

## Design Principles

1. **Cyberpunk Control Room** — Dark theme เป็นพื้น, cyan/neon accent ชี้ข้อมูลสำคัญ
2. **Information Density ที่ควบคุมได้** — ข้อมูลเยอะแต่ไม่รก, ใช้ hierarchy + spacing จัดลำดับความสำคัญ
3. **Real-time First** — WebSocket data updates ต้อง smooth, latency ต่ำ
4. **Progressive Disclosure** — ซ่อนรายละเอียดที่ไม่จำเป็น, แสดงเฉพาะเมื่อต้องการ
5. **Consistency** — component vocabulary เหมือนกันทั้งแอป

## Accessibility & Inclusion

- WCAG AA compliance (contrast ≥ 4.5:1 สำหรับ body text)
- supports prefers-reduced-motion
- semantic HTML structure
