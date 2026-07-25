# First Real Track Record — แผนงานใหญ่ (เริ่ม 2026-07-23)

> เป้าหมายตาม North-star ใน `PRIVATE_FUND_ROADMAP.md`
> **ยังไม่ live trading** — testnet เท่านั้น ตาม `CLAUDE.md` § Never

## นิยามว่าเสร็จ (ตรวจได้ ไม่ใช่ความเห็น)

**หนึ่งเดือนรายงานที่ปิดผนึกด้วย `FundV2Store.lock_period`** ซึ่ง:

1. NAV / XIRR / strategy attribution คำนวณจาก **fill จริง** บน Binance Spot Testnet
2. ค่าธรรมเนียมมาจาก **commission จริง** ไม่ใช่ค่าประมาณ (`allFeesActual === true`)
3. reconciliation ระหว่าง D1 กับ exchange ไม่มี exception ค้าง หรือถูก resolve
   แบบ four-eyes (maker ≠ checker) แล้ว
4. governance hash chain `verifyGovernanceChains()` = verified
5. **reproduce ได้ด้วยคำสั่งเดียว** จาก repo ที่ clone ใหม่

ถ้าข้อใดข้อหนึ่งไม่ผ่าน = ยังไม่เสร็จ ไม่มีการผ่อนเกณฑ์

## ทำไมโปรเจกต์นี้ ไม่ใช่ฟีเจอร์ใหม่

Roadmap ตั้งคำถามความสำเร็จไว้ 4 ข้อ วันนี้ตอบได้ด้วยข้อมูลจริง **1 ข้อ**
(ใครอนุมัติ) เครื่องจักรสร้างครบแล้ว — realized P/L จาก commission จริง, XIRR,
attribution, period lock, cron, abuse guards — **แต่ไม่เคยติดเครื่องสักครั้ง**

## ⚠️ สิ่งที่ต้องรับรู้ล่วงหน้า

E26–E28 พิสูจน์แล้วว่า grid **ไม่มี edge** เหนือ buy-and-hold
track record แรกจึงมีแนวโน้มเป็น **ผลตอบแทนที่แพ้ benchmark**
นั่นไม่ทำให้โปรเจกต์นี้ล้มเหลว — เป้าหมายคือพิสูจน์ว่า **ระบบบัญชีเชื่อถือได้**
ไม่ใช่ว่ากลยุทธ์ทำเงินได้ track record ที่ซื่อสัตย์และแพ้ benchmark
มีค่ามากกว่าตัวเลขสวยที่ตรวจย้อนไม่ได้

---

## P0 — ปลดบล็อก (ต้องคุณทำ ผมทำแทนไม่ได้)

ทั้งสามข้อเป็นการจัดการ credential / บัญชี ซึ่งอยู่นอกขอบเขตที่ agent ทำได้

| # | สิ่งที่ต้องทำ | อาการตอนนี้ |
|---|---|---|
| 1 | สร้าง **Binance Spot Testnet key ใหม่** (สิทธิ์ USER_DATA + trade, ตรวจ IP restriction) แล้วอัปเดต GitHub secrets `BINANCE_TESTNET_API_KEY` / `_SECRET` แล้ว redeploy เพื่อ sync Worker secrets | placement คืน `-2015 Invalid API-key, IP, or permissions` — testnet key หมดอายุ |
| 2 | เพิ่ม GitHub secret **`CLOUDFLARE_D1_API_TOKEN`** ที่มีสิทธิ์ D1 edit **หรือ** รัน `wrangler d1 migrations apply GOVERNANCE_DB --remote` เองครั้งเดียว | deploy token ได้ `7403 not authorized` → migration 0005 ยังไม่ apply → fill detail ไม่ถูกบันทึก realized P/L ยังเป็นค่าประมาณ |
| 3 | **เปิด R2** ใน Cloudflare Dashboard แล้วสร้าง bucket | `wrangler r2 bucket create` คืน `10042 enable R2 through the Dashboard` → fund-ops dashboard ยังเป็น demo |

**ข้อ 2 คือตัวบล็อกที่แพงที่สุด** — ถ้าไม่ apply migration 0005 ข้อ 2 ของ
"นิยามว่าเสร็จ" (fee จริง) จะผ่านไม่ได้เลย

---

## P1 — พิสูจน์ execution loop

- เดิน bot testnet จริงผ่าน four-eyes → fill จริง
- เปิด cron อัตโนมัติ (`GRID_CRON_ENABLED` + `GRID_CRON_SECRET` + repo secrets)
- ยืนยัน `aggregateFillsByOrder` + `computeRealizedCycles` ทำงานกับ commission จริง
  (`feeBasis: actual`) — โค้ดพร้อมแล้ว ยังไม่เคยเจอ fill จริง

## P2 — สะพาน D1 ↔ Python ledger ← **แกนของโปรเจกต์**

**ปัญหา**: ระบบมีสองบัญชีที่ไม่คุยกัน — grid fill อยู่ใน **D1 (TypeScript)**
ส่วน ledger/NAV/XIRR/attribution อยู่ใน **Python** ต่อให้ bot เทรดได้จริง
P/L ก็ไม่ไหลเข้า track record นี่คือหนี้สถาปัตยกรรมที่ยังไม่มีใครแตะ

**รูปแบบที่จะใช้** — ซ้ำแบบเดียวกับ Loop snapshot exporter → Aegis reader
ที่พิสูจน์แล้วว่าใช้ได้ (versioned JSON + validator ที่ fail closed):

1. **ฝั่ง TS**: exporter อ่าน `grid_bot_orders` ที่ `status = FILLED`
   → JSON versioned พร้อม source hash
2. **ฝั่ง Python**: importer แปลงเป็น `LedgerEvent.trade_fill` เข้า
   `AppendOnlyLedger`

**การตัดสินใจออกแบบที่ต้องล็อกก่อนเขียน**:

| ประเด็น | การตัดสินใจ |
|---|---|
| `external_id` (idempotency) | ใช้ `clientOrderId` ของ exchange — deterministic อยู่แล้วจาก `grid-runtime.ts` การ export ซ้ำจึงห้ามนับซ้ำ |
| `strategy_id` | = `botId` → ทำให้ `performance.py` attribution แยก P/L ต่อ bot ได้ทันที |
| `fee` ที่เป็นสินทรัพย์อื่น | commission อาจเป็น BNB หรือ `MIXED` → ต้องผ่าน approved-marks FX policy เดิม **ไม่มี mark = fail closed** ห้ามตีเป็น 0 |
| แถวที่ไม่มี fill detail | (migration 0005 ยังไม่ apply) **ห้าม export ด้วยค่าประมาณเงียบ ๆ** ต้อง fail closed หรือทำเครื่องหมาย provisional |
| ทิศทางข้อมูล | ทางเดียว D1 → Python เท่านั้น ไม่มี write กลับเข้า D1 จาก Python |

## P3 — track record จริง

daily close อัตโนมัติ → NAV (mark-to-market) → XIRR → attribution ต่อ bot →
benchmark → `operations_snapshot` → R2 → dashboard เลิกเป็น demo

## P4 — ปิดผนึกและตรวจสอบ

`lock_period` เดือนแรก + exception four-eyes + chain verify +
one-command reproduction

---

## ลำดับการลงมือ

P2 **ไม่ต้องรอ P0** — สะพานสร้างและทดสอบด้วย fixture ได้เลย แล้วค่อยเสียบ
ข้อมูลจริงเมื่อ P0 ปลดล็อก จึงเริ่มจาก P2 ระหว่างรอ
