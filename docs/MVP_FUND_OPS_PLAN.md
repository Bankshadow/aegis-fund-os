# MVP Implementation Plan — Fund Operations Cockpit

## MVP outcome

ให้ผู้ดำเนินการเห็น P/L และสถานะของหนึ่ง portfolio บนหนึ่ง platform แบบตรวจสอบย้อนกลับได้
โดยยังเป็น read-only: ไม่มี order placement, custody หรือเงินของผู้ลงทุน

## สถานะการพัฒนา (สัปดาห์ 1–8 + post-MVP #1 บางส่วน)

- `dynamic_grid.fund_ops.AppendOnlyLedger`: ledger ที่รับ event แบบ idempotent และ append-only
- P/L snapshot สำหรับ spot fills: realized/unrealized gross P/L, fees, carry และ adjustments
- `ReadOnlyPlatformConnector`: contract ที่ไม่มี method สำหรับส่งคำสั่งโดยตั้งใจ
- JSONL export เพื่อเก็บ source-linked audit trail และ unit tests สำหรับ flow หลัก
- SQLite event store ที่ replay ledger ได้และบังคับ `external_id` ไม่ซ้ำ
- Binance Spot read-only adapter สำหรับ balances/fills โดยมี HMAC signing และไม่รองรับ POST/DELETE
- **`ApprovedMarksFeeConverter`**: แปลงค่าธรรมเนียมที่ไม่ใช่ reporting asset ด้วย mark ที่ผู้อนุมัติ
  (เช่น `BNB/USDT=600`); fail-closed ถ้าไม่มี mark — CLI ส่งจาก `--mark` ชุดเดียว
- **Spot deposit/withdraw sync** → `EventType.TRANSFER` (`/sapi/v1/capital/deposit/hisrec`,
  `/sapi/v1/capital/withdraw/history`); non-reporting capital flows fail-closed
- **USDⓈ-M Futures funding sync** → `EventType.FUNDING` (`/fapi/v1/income`,
  `incomeType=FUNDING_FEE`) ใน account scope แยกจาก Spot; รวม collateral
  `TRANSFER` และ USDⓈ-M `userTrades` → `DERIVATIVE_FILL`
- **Spot distribution income sync** → `EventType.REBATE`
  (`/sapi/v1/asset/assetDividend`; launchpool/airdrop/referral) เข้า carry-P/L
  bucket ไม่ใช่ capital transfer (2026-07-18)
- **Multi-currency capital FX policy** (2026-07-18): deposit/withdraw/dividend
  ที่ไม่ใช่ reporting asset แปลงด้วย `capital_fx` mark ที่ผู้อนุมัติ แล้วบันทึก
  `original_asset/original_amount/fx_rate` ใน metadata; ไม่มี mark → fail-closed
  เหมือนเดิม. CLI ใช้ `--mark` ชุดเดียวเป็นทั้ง fee converter และ capital FX
- reconciliation สำหรับ spot inventory เทียบกับยอดแพลตฟอร์ม; mismatch จะทำให้ report เป็น `provisional`
- reporting-currency cash ledger: deposits/withdrawals, fills, fees, funding และ adjustments
  มีผลต่อยอด cash แต่ transfer ไม่ถูกนับเป็น performance P/L
- daily-close report (JSON) และ [Fund Operations Dashboard](../fund_ops_dashboard.html) แบบ static
- RBAC/audit foundation ที่อนุญาตเฉพาะ read-only sync และปฏิเสธ `place_order` ทุก role

## งานหลัง MVP ตามลำดับ

1. ~~เพิ่ม Binance funding/transfers และ fee conversion ที่อ้างอิง price source ที่อนุมัติ~~
   **เสร็จ (2026-07-15 → 07-18):** fee conversion + Spot TRANSFER sync,
   USDⓈ-M Futures funding + collateral transfer + derivatives fills,
   Spot distribution income และ multi-currency capital FX policy
2. ~~ขยาย ledger เป็น derivatives, FX และ multi-currency พร้อม valuation policy~~
   **เสร็จ:** derivatives fills/positions, `ApprovedFxValuation` สำหรับ balances,
   capital FX สำหรับ transfer/income, และ (2026-07-19) **NAV valuation เข้า
   daily-close** — `compute_nav` คิดค่า spot (qty×mark) + derivative
   mark-to-market (unrealized), fail-closed เมื่อ position ที่เปิดอยู่ไม่มี mark
   (ไม่ตีเป็น 0 เงียบๆ); daily-close job persist close ผ่าน
   `FundV2Store.record_close` (idempotent upsert, รักษา locked) และ missing-mark
   ถูกบันทึกเป็น exception ที่บล็อกการ lock
3. ~~เพิ่ม reconciliation ของ cash/fills และ exception review/approval persistence~~
   **เสร็จ:** exception idempotent + four-eyes resolve + lock-blocking ใน
   `FundV2Store`; daily-close job persist ทั้ง exceptions และ close record
4. ~~เพิ่ม NAV, TWR/MWR, benchmark, strategy attribution และ reporting-period lock~~
   **เสร็จเกือบครบ (2026-07-20):** NAV เข้า daily-close แล้ว (ข้อ 2), TWR มีอยู่ที่
   `fund_v2.time_weighted_return`, และ `dynamic_grid/performance.py` เพิ่ม
   **MWR/XIRR** (bisection, fail-closed เมื่อ flow ไม่ครบ/ไม่มีสลับเครื่องหมาย),
   **strategy attribution** (แบ่ง ledger ตาม `strategy_id` แล้ว replay ผ่าน
   snapshot engine เดิม → attribution ไม่มีทางขัดกับตัวเลขรวม และ sell ที่ไม่มี
   inventory ใน strategy นั้น fail closed) และ **benchmark comparison**
   (excess return; start ≤ 0 fail closed). 12 tests ใน
   `tests/test_fund_performance.py` (อยู่ใน gate pattern `test_fund*`)
   **reporting-period lock เสร็จแล้ว (2026-07-20):** `FundV2Store.lock_period`
   ปิดงวดรายเดือน (`YYYY-MM`) หรือรายไตรมาส (`YYYY-Qn`) ได้ ต่อเมื่อ daily close
   ในงวดนั้น lock ครบ (maker/checker ทำที่ระดับ daily แล้ว) และไม่มี exception
   ค้าง; ปิดซ้ำถูกปฏิเสธ **และมีเขี้ยวจริง** — `record_close`, `add_exception`
   และ `lock_close` จะโยน `PermissionError` เมื่อวันที่นั้นอยู่ในงวดที่ปิดแล้ว
   โดยตรวจทั้งรูปเดือนและไตรมาสของวันที่ (ปิด Q3 แล้วเขียนวันที่ในเดือน ส.ค.
   ก็ไม่ผ่าน) 12 tests ใน `tests/test_fund_period_lock.py`
5. ~~ต่อ dashboard เข้ากับ service ภายในที่อ่านจาก SQLite เท่านั้น~~
   **เสร็จบางส่วน (2026-07-19):** `getOperationsSnapshot` อ่าน snapshot ตามลำดับ
   R2 object (binding `OPERATIONS_BUCKET`, key `operations_snapshot.json`) →
   `AEGIS_OPERATIONS_SNAPSHOT_JSON` → path → demo fallback; รับเฉพาะ
   `persisted_snapshot` ที่ `ready/provisional` เท่านั้น มิฉะนั้น fail closed
   (`src/lib/operations-snapshot.ts`, 7 tests). Portfolio/Reconciliation แสดง
   real data เมื่อ snapshot ถูก feed. **การเปิดใช้ R2 (ข้อมูลจริง):**
   (1) `wrangler r2 bucket create aegis-operations-snapshots`, (2) uncomment
   `r2_buckets` ใน `wrangler.jsonc`, (3) generate snapshot ด้วย
   `python operations_snapshot_cli.py ...` แล้ว
   `wrangler r2 object put aegis-operations-snapshots/operations_snapshot.json --file=...`
   R2 เป็น binding (เหมือน D1) จึงเลี่ยงข้อจำกัด escaping/ขนาดของ inline env JSON

## Definition of Done สำหรับ MVP

- sync ซ้ำแล้วไม่เกิด event ซ้ำ
- balance, position และ fill reconcile กับ platform พร้อมรายการ exception
- reporting-currency cash จะ reconcile ได้เมื่อ deposit/withdrawal ถูก import เป็น transfer event ครบ
- P/L report drill-down ถึง `external_id` และ `source_ref` ได้
- transfer ไม่ถูกนับเป็น performance P/L
- credentials เป็น read-only และอยู่นอก repository/logs

## วิธีทดลองแบบ read-only

1. สร้าง API key ที่มี permission อ่านข้อมูลเท่านั้นและจำกัด IP ตามนโยบายของ platform
2. ตั้ง `BINANCE_API_KEY` และ `BINANCE_API_SECRET` ใน environment ของเครื่อง—not in `.env` ที่ commit
3. เรียก connector จาก job ภายใน, persist `ConnectorSync.events` ด้วย `SQLiteLedgerStore`,
   แล้วสร้าง report ที่ `results/fund_ops_daily_report.json`
4. เปิด `http://localhost:8931/fund_ops_dashboard.html`

หน้าจอ Fund Operations แบ่งเป็น 4 หน้า:

1. `fund_ops_dashboard.html` — P/L, cash และ positions
2. `fund_ops_accounts.html` — platform/account และ balances
3. `fund_ops_ledger.html` — append-only events พร้อม source reference
4. `fund_ops_reconciliation.html` — exceptions และ daily-close status
5. `fund_ops_portfolio.html` — portfolio close และ track-record summary
6. `fund_ops_risk.html` — paper-only risk controls

คำสั่งรัน flow ทั้งหมด:

```powershell
$env:BINANCE_API_KEY = 'your-read-only-key'
$env:BINANCE_API_SECRET = 'your-read-only-secret'
python fund_ops_cli.py --account-id ops-spot --symbol BTCUSDT `
  --mark BTC/USDT=65000 --mark BNB/USDT=600
```

ก่อนรันจริง ต้องแทนราคาด้วยราคาปิดตาม valuation policy ที่อนุมัติแล้ว (รวม mark ของ
commission asset เช่น BNB ถ้าแพลตฟอร์มคิดค่าธรรมเนียมเป็น BNB) และใช้ key
ที่เปิดสิทธิ์อ่านข้อมูลเท่านั้น

สำหรับ USDⓈ-M funding อย่างเดียว (ไม่มีการส่งคำสั่ง):

```powershell
python fund_ops_cli.py --account-id ops-futures --source usdm-funding
```

รายงาน Futures funding จะยังเป็น `provisional` จนกว่าจะมี derivatives fills/positions
และ collateral transfers สำหรับกระทบยอดครบ

## Guardrails

- ไม่เพิ่ม method ส่ง live order ใน connector ชุดนี้
- กลยุทธ์ต้องผ่าน validation gate ของระบบเดิมแยกต่างหาก
- ก่อนรับเงินบุคคลอื่น ต้องมี controlled-live evidence และตรวจข้อกฎหมาย/ใบอนุญาตตามเขตอำนาจศาล
