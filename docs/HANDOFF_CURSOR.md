# Handoff to Cursor — Dynamic Grid Trading System

> อ่านตามลำดับ: (1) เป้าหมายใหม่ (2) ห้ามทำ (3) สถานะปัจจุบัน (4) งานถัดไป (5) กติกา

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

## 3. สถานะปัจจุบัน (v3.19 / E25, 2026-07-15)

**แนะนำ (วิจัยสาย A)**: Dual 75/25 **rule-based** + percentile-rank regime  
**สาย B**: `dual_pct` wired; จูนแล้ว (E23–E25) แต่ **ยังแพ้ cash** — E23 ดีสุด (−0.0078)  
**ไม่แนะนำ**: RL เป็น default; `require_edge` อย่างเดียว; ลดเกณฑ์ ValidationGate;
แยก short_cfg เป็น default (E24 แย่กว่า); conservative-only search (E25 ยัง < 0)

| # | ผลสั้นๆ |
|---|---|
| E21 dual_pct promotion | wiring เสร็จ; FAIL — เลือก cash |
| E22 dual vs cash | PASS วินิจฉัย — `negative_edge_trading` |
| E23 dual tune | FAIL — ดีขึ้น (+0.03) แต่ mean robust ยังติดลบ / ไม่ promote |
| **E24 short_cfg** | **FAIL — −0.0205; แย่กว่า E23** |
| **E25 conservative** | **FAIL — −0.0154; ยังแพ้ cash** |

---

## 4. งานที่ควรทำต่อ

1. Dual Line-B: geometry-only (E23–E25) หมดแรงแล้ว — ทดลองสมมติฐานใหม่ที่ประกาศก่อนรัน
   (เช่น funding/relative A/B) หรือยอมรับ cash เป็น default สาย B แล้วหันไป fund-ops
2. ถ้ากลับมาทำ RL: เปลี่ยนสมมติฐาน (state/reward) แล้ว walk-forward ใหม่
3. **Fund-ops (ลำดับปัจจุบัน):** Spot fee conversion + TRANSFER sync และ USDⓈ-M
   funding sync เสร็จแล้ว — ถัดไป derivatives fills/positions + collateral transfer
   ก่อน FX/multi-currency และ exception approval persistence
   (ดู `docs/MVP_FUND_OPS_PLAN.md`)

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
