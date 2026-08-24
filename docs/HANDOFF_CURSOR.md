# Handoff to Cursor — Dynamic Grid Trading System

> อ่านตามลำดับ: (1) เป้าหมายใหม่ (2) ห้ามทำ (3) สถานะปัจจุบัน (4) งานถัดไป (5) กติกา

---

## 0-NEW. อ่านก่อนสุด — เปลี่ยนทิศ: research → education (2026-07-25)

**ผู้ใช้อนุมัติแล้ว: เปลี่ยนหน้าตาผลิตภัณฑ์จาก "bot ที่เทรด" เป็น "เครื่องมือสอน"
โดยใช้ engine ตัวเดิม** เหตุผล: E20–E29 คือ 9 การทดลองติดกันที่ไม่ผ่าน gate —
geometry, regime filter (E27), trailing (E28), exposure cap (E29) ไม่มีตัวไหน
ทำให้ grid มี edge จริงบน AOT รายวัน การสร้าง ops/safety ห่อกลยุทธ์ที่ยังไม่มี
edge คือปัญหาที่แท้จริง ส่วน engine + walk-forward harness + evidence ledger
นั้นดีจริง และการสอนว่า **ทำไม grid ถึงแพ้** ไม่ต้องใช้ edge เลย

**ที่ทำเสร็จ (verify สดในแอปทุกหน้า · commit แล้ว):**
1. `/walk-forward` — ตาราง OOS ราย fold + verdict + สรุป
2. `/walk-forward-compare` — E26 → E28 → E29 ข้างกัน + คำอธิบายตรงไปตรงมา
3. ต้นทุนปรับได้ใน `/walk-forward` — Thai retail / 0 / สูง
4. `/walk-forward-overfit` — บทเรียน overfitting

**กติกาสำคัญที่ต้องรักษา:** walk-forward เป็น **pure function เดียว**
`src/lib/aot-walkforward.ts` ใช้ร่วมกันทั้ง CLI research (ตอนนี้เป็น wrapper บาง ๆ)
และ server functions ในแอป มีเทสต์ pin ค่า E26/E28/E29 + invariant 6/18 fold
→ **หน้า education drift จากงานวิจัยไม่ได้** ห้ามแยกสองทาง

**สองคำอ้างที่ "วัดแล้ว" และผลค้านสัญชาตญาณ — เขียน copy ตามหลักฐาน ไม่ใช่ตามที่คิด:**
- "grid แพ้เพราะค่าธรรมเนียม" **ผิด**: ต้นทุน 0 alpha ยัง ≈ −11.2 → ต้นทุนไม่ใช่สาเหตุ
- "เลือก geometry ที่ชนะ in-sample" **ไม่มีค่า**: ตรงกับ OOS 3/18 = 16.7% ซึ่ง
  เท่ากับสุ่มเป๊ะ (1/6); อันดับเฉลี่ย 3.56 vs สุ่ม 3.50; แม้เลือกแบบรู้อนาคตก็ได้
  −16.61 ยังติดลบหนัก

**ความสมบูรณ์ของงานวิจัย:** Overfitting Lab วัด OOS ของ candidate ที่ถูกปฏิเสธ —
เป็น opt-in (`diagnostics`) และ **ไม่นับใน `runCount`** เพราะไม่มีการเลือกอะไรจากมัน
ถ้านับจะรายงาน multiple-testing count ผิด · มีเทสต์ pin ว่า runCount ยัง 324

**งานถัดไป:** เอาไปให้นักเรียนใช้จริง แล้วให้ feedback เลือกว่า slice 5 คืออะไร
**อย่าเพิ่มหน้าใหม่แบบเดา** — การสร้างของที่ไม่มีคนใช้คือสิ่งที่ pivot นี้กำลังแก้
ห้ามเทรดจริงเหมือนเดิม ทุกหน้าเป็น read-only research

บทความ Grok Bot ของ EXM7777 (2026-08-24) ถูก **กรอง** เข้า stack แล้ว:
`docs/GROK_BOT_LANES.md` + `agent/lanes.py` + `docs/vault/` — รับกติกา
one-job-per-lane / vault เหนือ memory / อนุมัติชนะ allow / ตรวจก่อน done
**ไม่ได้** ติดตั้ง 10 บอทรายได้ (UGC, outbound, paid media). BUILD 7 ยัง deferred.
slice 5 ยังมาจากนักเรียน ไม่ใช่จากบทความนั้น

---

## 0. อ่านก่อน — สถานะสด ณ 2026-07-23 (Graph L2/L3 + D1 migrations)

### สิ่งที่ทำใน session นี้ (verify แล้ว · gate SHIP)

วิเคราะห์ Graph Engineering (0xCodez) เทียบโครงสร้างเดิม แล้วลงมือเฉพาะ L2+L3
โดยไม่ให้กระทบ placement path:

| ชั้น | สิ่งที่เพิ่ม | Firewall |
|---|---|---|
| **L2 harness** | `agent/graph_contracts.py`, `agent/graph_ops.py`, diamond แรก `python -m agent.diamonds.runtime_safety_review` | ไม่ import Fund OS / exchange |
| **L3 runtime** | `grid-runtime-graph.ts` (severity route), `grid-runtime-fleet.ts` (opt-in dry-loop + telemetry), persist route บน `grid_runtime_runs` | ไม่เรียก LLM; place ยังผ่าน `grid-runtime-safety.ts` เท่านั้น |

รายละเอียดสำคัญ:

1. **Migration D1 remote ครบ** — apply **0004–0007** บน `GOVERNANCE_DB`
   (ก่อนหน้าค้าง 0004–0006 ด้วย); local มี 0007; remote list = no pending;
   คอลัมน์ `route_severity` / `route_action` / `work_remaining` / `deferred` มีจริง
2. **Route classification** — ทุก reconcile ได้ `route`; cron/sync-all ได้ `fleet` +
   `telemetry`; cockpit `/bots` แสดงแผง Recent runtime routes
3. **Dry-loop default OFF** — เปิดวัดด้วย `GRID_RECONCILE_DRY_LOOP=true`
   (cap max 5); playbook: `docs/DRY_LOOP_MEASUREMENT.md`
4. **L2 diamond** — findings 0 / `quick_pass` บนแหล่งปัจจุบัน;
   `tests.test_agent_graph` อยู่ใน `gate/verify.ps1`
5. Docs อัปเดต: `docs/AGENT_STACK.md` (BUILD 7.5), `ROUTING.md`,
   `docs/GRID_BOT_PHASE3.md`, `docs/DRY_LOOP_MEASUREMENT.md`, `STATE.md`

**Done check:** `powershell -File gate/verify.ps1` → SHIP; L3 node tests
(graph/fleet/reconcile/safety) ผ่าน; diamond CLI สะอาด

### งานถัดไปแนะนำ (เรียง ROI)

1. **วัด dry-loop บน testnet** — ตั้ง Worker secret ชั่วคราวตาม
   `docs/DRY_LOOP_MEASUREMENT.md` → Sync all → อ่าน `telemetry`
   (`avgPassesPerBot`, `backlogStillDeferred`) → ตัดสินเปิดค้างหรือปิด
2. ถ้า `backlogStillDeferred=true` บ่อย → เพิ่ม `GRID_MAX_REPLENISHMENTS_PER_RUN`
   ก่อน อย่าเพิ่ม maxRounds
3. (ถ้าต้องการ) L2 diamond ที่สองแบบมี trigger — เช่น route-auth audit ของ
   `src/routes/` เมื่อ diff ใหญ่; อย่าติดตั้ง BUILD 7 swarm speculative
4. (วิจัย) parallel seeds/folds ใน L1 — ไม่แตะ execution

### ยังไม่ทำ / ห้ามทำในรอบถัดไป

- อย่าใส่ LLM ใน reconcile/place path
- อย่าเปิด dry-loop ถาวรโดยไม่มี telemetry
- อย่า spawn subagent/swarm เป็น default (`CLAUDE.md` / ROUTING BUILD 7 ยัง deferred)
- Live orders / third-party capital ยังห้าม

### Deploy / commit note

โค้ด L2/L3 + docs อยู่ใน working tree ของ session นี้ — **ยังไม่ commit จนกว่า user
จะขอ** (ตามกติกา repo). หลัง commit/deploy อย่าลืมว่า migration remote apply แล้ว
แต่ Worker bundle ต้อง deploy ใหม่ถ้าต้องการ telemetry/UI บน production

รายละเอียดยาว: `STATE.md` (Verified since previous handoff) +
`docs/GRID_BOT_PHASE3.md` § Runtime graph / dry-loop

---

## 0b. บันทึกเก่า — สถานะ ณ 2026-07-19 (ยังอ้างอิงได้)

**หมายเหตุ:** รายการ deploy queue ด้านล่างอาจถูก deploy ไปบางส่วนแล้วหลังวันที่นั้น —
ตรวจ `STATE.md` / git log ก่อนสมมติว่ายังค้าง

Deploy queue ที่เคยค้าง (2026-07-19): orphaned-fill rollback, N+1 serverTime,
route un-nesting, draft toast, route titles, `/audit` hash chain จริง, Phase 3
grid runtime loop (human-triggered). Cron ภายนอก + safety plane ถูกเพิ่มหลังวันที่นั้น
(ดู Phase 3 doc + migration 0006/0007)

**ต้องให้ user ทำเอง (agent ทำแทนไม่ได้ — ห้ามกรอก credential/ทำ auth):**
- four-eyes approval + Start bot บน production ต้อง login Access เป็น identity
  ที่สอง แล้ว approve/start เอง; ใช้ปุ่ม Reconcile / Sync all ตาม runbook ใน `STATE.md`

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
4. **Grid bot runtime + graph layer (2026-07-23):** Phase 3 loop + safety +
   route persist (0007) + opt-in dry-loop telemetry พร้อมแล้ว — ถัดไปวัด dry-loop
   ตาม `docs/DRY_LOOP_MEASUREMENT.md` ก่อนเปิดถาวร; ดู §0 ด้านบน
5. **Agent stack graph (BUILD 7.5):** scaffold + diamond แรกเสร็จ; BUILD 7 fan-outs
   ยัง deferred จนเข้า trigger ใน `ROUTING.md`

### Agent stack (ปรับจาก Avid Fable5+GPT-5.6)

อ่าน `docs/AGENT_STACK.md` + `ROUTING.md` + `AGENTS.md`
- Driver ถูก / Advisor (Fable) เป็นกรัม / **gate เป็นโหวตสุดท้าย**
- ก่อน merge หรือเคลมว่าทำเสร็จ: `powershell -File gate/verify.ps1`
- อ่าน/เขียน `STATE.md` ทุก session
- Graph contracts: `python -m unittest tests.test_agent_graph` ·
  `python -m agent.diamonds.runtime_safety_review`

---

## 5. กติกา (ย่อ)

ประกาศเกณฑ์ก่อนรัน · held-out · ≥3 seeds · synthetic ≠ หลักฐานจริง · ห้าม transfer ข้าม scale/TF · บันทึกผลลบ · RL ต้องทน walk-forward บนข้อมูลจริง · นับเฉพาะ engaged · ห้ามลด ValidationGate · done = ข้อเท็จจริงจาก environment ไม่ใช่ความเห็นโมเดล · L2 harness ห้ามแตะ place path · L3 runtime ห้าม LLM

---

## 6. Smoke

```
powershell -File gate/verify.ps1
python -m unittest tests.test_strategy_framework
python -m unittest tests.test_agent_graph
python -m agent.diamonds.runtime_safety_review
python dual_tune_demo.py
python diagnose_dual_cash_demo.py
python run_demo.py --fast
python agent/router.py "promote dual after E23?"
```
