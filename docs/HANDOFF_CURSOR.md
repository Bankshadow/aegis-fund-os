# Handoff to Cursor — Dynamic Grid Trading System

> อ่านตามลำดับ: (1) เป้าหมายใหม่ (2) ห้ามทำ (3) สถานะปัจจุบัน (4) งานถัดไป (5) กติกา

---

## 0. อ่านก่อน — สถานะสด ณ 2026-07-19 (session handoff)

**⚠️ มี fix + feature ที่ verify แล้วค้างใน working tree ยังไม่ commit และยังไม่
deploy — production เสิร์ฟ bundle เก่าที่มีบั๊ก route จริงอยู่.** งานแรกของ session
ถัดไปควรเป็น commit + push (ขออนุญาต user ก่อน push เพราะกระทบ production public)
แล้วปล่อยทั้งชุด:

Deploy queue (ทุกตัว: tsc สะอาด · frontend tests 39/39 · build ผ่าน · gate SHIP):

1. Orphaned-fill rollback — `placeTestnetGrid` + `startBinanceTestnetGridBot`
   โยน `OrphanedTestnetOrdersError` แทนกลืน error เมื่อ cancel ล้ม (fill แล้ว)
2. N+1 serverTime — sync `/api/v3/time` ครั้งเดียวต่อการวางกริด
3. **Route un-nesting** — `bots_.$botId_.orders.tsx` / `_.events.tsx`
   (เดิม nested ใต้ detail ที่ไม่มี `<Outlet/>` → สองหน้านี้เข้าไม่ถึงบน prod)
4. Toast เมื่อ Save Draft ยังไม่ติ๊ก risk ack (`bots_.new.tsx`)
5. Route titles ให้ bot detail / orders / events
6. **`/audit` ใช้ hash chain จริง** — เลิกโชว์ "verified" ปลอมจาก `AUDIT_EVENTS`
   fixture (ลบ fixture แล้ว); + แก้ latent type bug `profitByBot` ใน `bots.tsx`
7. **Grid runtime loop (Phase 3, 2026-07-19)** — fill tracking + replenishment:
   `grid-runtime.ts` planner, `recordGridSync`, `syncBinanceTestnetGridBot`,
   event ใหม่ `testnet.grid_synced`, ปุ่ม "Reconcile fills" บนหน้า Grid Profit
   (ดู `docs/GRID_BOT_PHASE3.md`). ไม่มี cron อัตโนมัติ — trigger ด้วยมือต่อรอบ

**ยังไม่ทำ (แนะนำทำในชุด deploy เดียวกัน):**
- หน้า Bot Audit Events ต่อบอท (`/bots/$botId/events`) ยังทิ้ง `event.payload`
  ทั้งหมด — ย้าย pattern payload+hash จาก `/audit` ที่เพิ่งทำมาใช้
- TOCTOU: re-check balance ก่อนวางแต่ละออเดอร์ (execution slice, ข้อ 4 ของ audit)

**ต้องให้ user ทำเอง (agent ทำแทนไม่ได้ — ห้ามกรอก credential/ทำ auth):**
- four-eyes approval + Start bot บน production ต้อง login Access เป็น identity
  ที่สอง (`bankshadow31@gmail.com`) แล้ว approve/start เอง; หลังจากนั้นใช้ปุ่ม
  "Reconcile fills" ไล่ loop ดู fill → replenishment (runbook เต็มใน `STATE.md`)

**สถานะ auth:** production กลับมาอยู่หลัง Cloudflare Access แล้ว (ทุก route redirect
ไป Email-OTP) — ช่องโหว่ public-access เดิมดูเหมือนถูกแก้แล้ว. ทดสอบ prod ตรงๆ
ไม่ได้ ให้ใช้ local `wrangler dev` + local D1 (migrations 0001–0003 apply ไว้แล้ว).
launch.json มี `fund-command-center` (vite) และ `fund-command-center-worker`
(wrangler :8787).

รายละเอียดเต็มของสิ่งที่ทำ: `docs/WORKLOG_2026-07-17.md` + `STATE.md` (Last session).

---

## 1. เป้าหมายใหม่

เปลี่ยนจาก research engine อย่างเดียว ไปสู่ **multi-platform trading operations**
ที่สร้าง P/L ledger, reconciliation และ audit trail ได้ครบ เพื่อสะสม track record
สำหรับ private-fund readiness. อ่าน `docs/PRIVATE_FUND_ROADMAP.md` ก่อนออกแบบ connector,
execution หรือ reporting ทุกครั้ง

## 2. ก่อนแตะโค้ด

- **ยังไม่พร้อมเทรดเงินจริง** — อนุญาตเฉพาะ read-only connector หรือ paper trading;
  ห้ามส่ง live order และห้ามรับ/บริหารเงินของบุคคลอื่น
- **RL**: ห้ามใช้ Q synthetic (`results/q_table.json` ฯลฯ)
  - E19: primary ผ่านบน BTC/4h split เดียว
  - **E20 walk-forward: ไม่ผ่าน (3/6 = 50%)** → อย่าถือว่า RL พร้อมใช้แม้บน BTC/4h
- ทุกทดลอง: ประกาศเกณฑ์ก่อนรัน, ≥3 seeds, held-out, รายงานผลลบ
- อ่าน `docs/VALIDATION_LOG.md` (E1–E23)

---

## 3. สถานะปัจจุบัน (v3.19 / D1, 2026-07-17)

**แนะนำ (วิจัยสาย A)**: Dual 75/25 **rule-based** + percentile-rank regime  
**สาย B**: 🔒 **default = cash (D1, 2026-07-17)** — dual จูนครบทุก candidate ที่ประกาศ
(E21–E25) แล้วยังแพ้ cash; ปิดสาย dual tuning จนกว่ามีสมมติฐานระดับกลไกใหม่
(เงื่อนไขใน `VALIDATION_LOG.md` § D1)  
**ไม่แนะนำ**: RL เป็น default; `require_edge` อย่างเดียว; ลดเกณฑ์ ValidationGate;
แยก short_cfg เป็น default (E24 แย่กว่า); conservative-only search (E25 ยัง < 0);
reuse funding/relative (E17/E18 fail เดี่ยวทั้งคู่) โดยไม่มีกลไกใหม่

| # | ผลสั้นๆ |
|---|---|
| E21 dual_pct promotion | wiring เสร็จ; FAIL — เลือก cash |
| E22 dual vs cash | PASS วินิจฉัย — `negative_edge_trading` |
| E23 dual tune | FAIL — ดีขึ้น (+0.03) แต่ mean robust ยังติดลบ / ไม่ promote |
| **E24 short_cfg** | **FAIL — −0.0205; แย่กว่า E23** |
| **E25 conservative** | **FAIL — −0.0154; ยังแพ้ cash** |

---

## 4. งานที่ควรทำต่อ

1. ~~Dual Line-B~~ **ปิดแล้ว (D1)** — cash คือ default สาย B; อย่ากลับมาจูน dual
   เว้นแต่มีสมมติฐานระดับกลไกใหม่ที่ผ่านเงื่อนไข D1; แรงหลักไป fund-ops (ข้อ 3)
2. ถ้ากลับมาทำ RL: เปลี่ยนสมมติฐาน (state/reward) แล้ว walk-forward ใหม่
3. **Fund-ops (ลำดับปัจจุบัน):** Spot fee/TRANSFER/dividend sync, USDⓈ-M
   funding + collateral + derivatives fills, และ multi-currency capital FX policy
   เสร็จแล้ว (2026-07-18) — ถัดไป persisted derivatives position valuation เข้า
   daily-close และ exception review/approval persistence (ดู
   `docs/MVP_FUND_OPS_PLAN.md`)
4. **Grid bot runtime (Phase 3 เสร็จ 2026-07-19):** loop แบบ human-triggered
   พร้อมแล้ว — ถัดไปถ้าต้องการ ให้ user ตัดสินใจเรื่อง automatic scheduler
   (cron/Durable Object) และ realized-cycle P/L accounting (ดู
   `docs/GRID_BOT_PHASE3.md`)

### Agent stack (ปรับจาก Avid Fable5+GPT-5.6)

อ่าน `docs/AGENT_STACK.md` + `ROUTING.md` + `AGENTS.md`
- Driver ถูก / Advisor (Fable) เป็นกรัม / **gate เป็นโหวตสุดท้าย**
- ก่อน merge หรือเคลมว่าทำเสร็จ: `powershell -File gate/verify.ps1`
- อ่าน/เขียน `STATE.md` ทุก session

---

## 5. กติกา (ย่อ)

ประกาศเกณฑ์ก่อนรัน · held-out · ≥3 seeds · synthetic ≠ หลักฐานจริง · ห้าม transfer ข้าม scale/TF · บันทึกผลลบ · RL ต้องทน walk-forward บนข้อมูลจริง · นับเฉพาะ engaged · ห้ามลด ValidationGate · done = ข้อเท็จจริงจาก environment ไม่ใช่ความเห็นโมเดล

---

## 6. Smoke

```
powershell -File gate/verify.ps1
python -m unittest tests.test_strategy_framework
python dual_tune_demo.py
python diagnose_dual_cash_demo.py
python run_demo.py --fast
python agent/router.py "promote dual after E23?"
```
