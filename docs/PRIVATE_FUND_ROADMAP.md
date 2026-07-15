# เป้าหมายใหม่: Multi-Platform Trading Operations → Private Fund Readiness

> สถานะปัจจุบัน: ระบบวิจัยและ backtest เท่านั้น การเชื่อมต่อใด ๆ เริ่มจาก
> **read-only / paper trading**; ห้ามส่ง live order จนกว่าจะผ่านเกณฑ์ด้านกลยุทธ์,
> ความเสี่ยง, reconciliation และการอนุมัติอย่างเป็นลายลักษณ์อักษร

## North-star

พัฒนาระบบจาก strategy research engine ไปเป็น **ศูนย์กลางการปฏิบัติการลงทุน
หลายแพลตฟอร์ม** ที่มี single source of truth สำหรับเงินทุน, สถานะ, ความเสี่ยง และ
กำไร/ขาดทุน (P/L) ที่ตรวจสอบย้อนกลับได้ครบถ้วน เพื่อสร้าง track record ที่เชื่อถือได้
ก่อนยกระดับสู่การบริหารเงินแบบ private fund ตามกฎหมายและใบอนุญาตที่เกี่ยวข้อง

ความสำเร็จไม่ใช่เพียงเชื่อม API ได้หรือมีผลตอบแทนดี แต่ต้องตอบได้ทุกเวลา:

1. เงินอยู่ที่ใด, เป็นของบัญชีหรือ mandate ใด, และใช้ได้จริงเท่าไร
2. P/L ของแต่ละกลยุทธ์, สินทรัพย์, แพลตฟอร์ม และช่วงเวลาเป็นเท่าไร โดยรวมทุกต้นทุน
3. ยอดในระบบตรงกับยอดจากแพลตฟอร์มหรือไม่ และความต่างได้รับการอธิบาย/อนุมัติหรือยัง
4. ใครอนุมัติการเปลี่ยนแปลง, การส่งคำสั่ง และการปรับปรุงรายการย้อนหลัง

## ขอบเขตเป้าหมาย

| เสาหลัก | เป้าหมาย |
|---|---|
| Platform connectivity | adapter มาตรฐานสำหรับ exchange, broker, custody และบัญชีธนาคาร/fiat โดยเริ่มจาก read-only |
| Portfolio & risk | portfolio view ข้ามแพลตฟอร์ม, exposure, leverage, concentration, cash และ limit ที่บังคับใช้ได้ |
| P/L ledger | immutable, double-entry-style event ledger สำหรับ order, fill, fee, funding, interest, transfer, adjustment และ valuation |
| Reconciliation | กระทบยอด balances, positions, fills และ cash flow กับข้อมูลต้นทาง พร้อม exception workflow |
| Track record | NAV/equity curve, realized/unrealized P/L, TWR/MWR, drawdown, benchmark และ strategy attribution ที่ reproducible |
| Governance | role-based access, audit trail, approval workflow, key management, reporting retention และ controls ที่พร้อมต่อยอดตามข้อกฎหมาย |

## ลำดับการส่งมอบ

### Phase 0 — Data model และ P/L ledger (ก่อนเชื่อม live)

- กำหนด canonical IDs: `account`, `platform`, `portfolio`, `strategy`, `instrument`,
  `order`, `execution`, `transfer`, `ledger_entry`, `valuation` และ `reporting_period`
- บันทึกทุกเหตุการณ์แบบ append-only พร้อมเวลา, แหล่งข้อมูล, reference ID และ version
- คำนวณ realized/unrealized P/L แยก gross/net; net ต้องรวม fees, spread/slippage,
  funding, borrow/interest, rebates, FX และการปรับปรุง
- นิยาม valuation policy, timezone/close-of-day, FX rates และวิธี lot accounting ที่คงที่

### Phase 1 — Read-only connectors และ reconciliation

- เชื่อมแพลตฟอร์มแรกแบบ read-only: balances, positions, orders, fills, funding และ transfers
- ทำ incremental sync ที่ idempotent, เก็บ raw payload และมี retry/rate-limit handling
- สร้าง daily reconciliation พร้อม tolerance, exception reason, owner และสถานะปิดงาน
- แสดง dashboard P/L และสถานะ data freshness ต่อ platform/account

### Phase 2 — Paper execution และ risk controls

- วาง execution adapter ที่แยกจาก strategy; ส่งได้เฉพาะ simulator/paper account
- เพิ่ม pre-trade limits, kill switch, order approval, exposure checks และ alerting
- เปรียบเทียบ simulated fill กับ market/exchange data และรายงาน execution quality

### Phase 3 — Controlled live pilot

- เปิด live เฉพาะบัญชีของผู้ดำเนินการและวงเงิน/สินทรัพย์ที่อนุมัติ
- ต้องมี dual approval สำหรับ credential, limit และ deployment; ไม่มี API key ใน source/log
- gate ก่อนขยาย: strategy validation ผ่าน, reconciliation ครบ, P/L report ปิดรอบได้,
  incident response ผ่านการซ้อม และมีผู้รับผิดชอบชัดเจน

### Phase 4 — Private-fund operating readiness

- แยกบัญชี/portfolio และสิทธิ์การเข้าถึงตาม mandate; หลีกเลี่ยง commingling โดยไม่มีนโยบายรองรับ
- สร้าง investor/fund reporting, NAV process, capital activity ledger และ record retention
- ให้ผู้เชี่ยวชาญด้านกฎหมาย/กำกับดูแลตรวจโครงสร้างนิติบุคคล, ใบอนุญาต, KYC/AML,
  marketing, custody, tax และข้อกำหนดในเขตอำนาจศาลก่อนรับเงินผู้อื่น

## เกณฑ์ “P/L ครบครัน”

รายงานจะถือว่าพร้อมใช้เมื่อทุกยอดสามารถ drill-down จาก portfolio → strategy →
platform/account → order/fill → ledger entry → source payload ได้ และมีผล reconciliation
ของรอบนั้นแนบอยู่ ยอด P/L ที่ยังมี exception เปิดอยู่ต้องถูกติดป้ายว่า provisional เสมอ

## สิ่งที่ไม่เปลี่ยน

ผลทดสอบเชิงกลยุทธ์ใน `VALIDATION_LOG.md` ยังคงเป็น gate แยกต่างหาก: connector หรือ
ledger ที่สมบูรณ์ **ไม่** ทำให้กลยุทธ์พร้อมเทรดเงินจริงโดยอัตโนมัติ และระบบยังไม่รับเงิน
หรือส่ง live order แทนบุคคลอื่นจนกว่าจะผ่าน Phase 3 และการกำกับดูแลที่เกี่ยวข้อง
