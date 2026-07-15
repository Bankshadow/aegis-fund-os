# Validation Log — สมุดบันทึกหลักฐานการทดสอบ (Evidence Ledger)

> เอกสารอ้างอิงถาวร: ทุกการทดลองสำคัญของระบบ บันทึกด้วยรูปแบบเดียวกัน —
> **คำถาม → เกณฑ์ (ประกาศก่อนรัน) → protocol → ผล → คำตัดสิน → คำสั่งทำซ้ำ**
> ผลลบถูกบันทึกเท่าเทียมกับผลบวก ไม่มีการเฉลี่ยกลบความล้มเหลว
> (รายละเอียดเชิงลึกอยู่ใน SYSTEM_SPEC.md ตามหัวข้อที่อ้างในแต่ละรายการ)

| # | วันที่ | การทดลอง | คำตัดสิน |
|---|---|---|---|
| E1 | 2026-07-06 | Static vs Dynamic บน synthetic 6 ตลาด | ✅ Dynamic ลด DD 77%→5% |
| E2 | 2026-07-06 | Regime module (v2) ablation | ✅ ผ่าน held-out seeds |
| E3 | 2026-07-06 | จูน regime params แรงเกิน | ❌ overfit — บทเรียน held-out บังคับ |
| E4 | 2026-07-07 | Multi-layer (v3) | ⚖️ ลด DD ทุกตลาด แลก return ครึ่งหนึ่ง |
| E5 | 2026-07-07 | Momentum confirmation (v3.1) | ✅ ผ่านตาม robust score (แพ้ถ้าวัด return) |
| E6 | 2026-07-08 | Walk-forward BTC จริงครั้งแรก (v3.2) | ❌ Static ชนะ Dynamic ทุกตัวชี้วัด |
| E7 | 2026-07-08 | Sub-window fix (v3.2.1) | ⚖️ ลด tail risk มาก แต่ไม่พลิกผล E6 |
| E8 | 2026-07-09 | Config ข้าม volatility scale (v3.6) | ❌ ไม่ transfer — zone เพี้ยนถึงราคาติดลบ |
| E9 | 2026-07-09 | Short grid บน bear จริง 2022 (v3.6) | ✅ +0.63%/DD 0.54% ขณะ long -3.94%/DD 8.83% |
| E10 | 2026-07-09 | RL governor บน synthetic (v3.6) | ✅ ชนะ rule-based บน held-out synthetic |
| E11 | 2026-07-09 | Dual-side 75/25 (v3.7) | ✅ ชนะ long-only ทั้ง 3 สนาม (synthetic/bear/bull) |
| E23 | 2026-07-11 | Tune dual under Line-B costs | ❌ ดีขึ้น (+0.03) แต่ mean robust ยังติดลบ |
| E24 | 2026-07-15 | Dual + separate short_cfg | ❌ แย่กว่า E23; เลือก cash |
| E25 | 2026-07-15 | Conservative geometry dual | ❌ mean −0.0154; ยังแพ้ cash |
| E12 | 2026-07-09 | RL เจอข้อมูลจริงครั้งแรก (v3.8) | ❌ พลิกกำไรเป็นขาดทุนบน bull จริง — ถอนคำแนะนำ RL |
| E13 | 2026-07-11 | Cross-asset router (v3.9) | ❌ **ยังไม่ผ่านเกณฑ์** — ผล router แยกไม่ออกจาก seed noise |
| E14 | 2026-07-11 | Percentile-rank regime (v3.10) | ✅ **ผ่าน** — pass rate 43%→83%, เกือบเท่าตัว |
| E15 | 2026-07-11 | Line-B integration: pct detector ใน framework | ⚖️ **gap ปิดแล้ว** — gate ยัง FAIL ทั้งคู่; pct ลด failure 57%→43% |
| E16 | 2026-07-11 | Edge filter ก่อน `_build()` | ✅ **กลไกผ่าน** — skip เมื่อ TP < round-trip; สมมติฐาน SOL/4h ต้นทุน>spacing ไม่ยืนยันกับ tuned params |
| E17 | 2026-07-11 | Funding-rate directional bias | ❌ **ไม่ผ่าน** — engaged 3/9 (33%); กลไก engage ได้ แต่ไม่ผ่านเกณฑ์ >50% |
| E18 | 2026-07-11 | Cross-asset relative-value (alt/BTC) | ❌ **ไม่ผ่าน** — engaged 2/6 (33%); แทน direction ได้แต่เพิ่ม DD ส่วนใหญ่ |
| E19 | 2026-07-11 | RL retrain บน BTC/4h จริง | ✅ **primary ผ่าน** — dual RL robust > rule บน held-out; secondary bull 1d ยังแพ้ |
| E20 | 2026-07-11 | Walk-forward RL บน BTC/4h | ❌ **ไม่ผ่าน** — engaged 3/6 (50%) ไม่เกินเกณฑ์ >50% |

---

## E25: Conservative-geometry dual tune — v3.19, 2026-07-15

**คำถาม**: ถ้าจำกัด search ให้เทรดถี่น้อยลง (spacing กว้าง / cooldown ยาว /
risk เล็กลง) จะดัน mean robust > 0 ภายใต้ต้นทุนจริงได้หรือไม่

**เกณฑ์ (ประกาศก่อนรัน)**: เหมือน E23; SPACE จำกัด levels 3–6, atr_mult 1.5–3,
risk 0.02–0.04, cooldown 40–80; shared base; ห้ามลด gate

**ผล** (`python dual_conservative_demo.py`):

| Dataset | untuned | tuned mean | delta |
|---|---|---|---|
| BTC 4h | -0.0479 | -0.0155 | +0.0324 |
| ETH 4h | -0.0188 | -0.0175 | +0.0013 |
| SOL 4h | -0.0472 | -0.0131 | +0.0342 |

Cross-asset tuned **−0.0154** (delta **+0.0226** vs untuned) — ดีกว่า E24
แต่แย่กว่า E23 (−0.0078)

| Criterion | Result |
|---|---|
| C1 mean robust > 0 | ❌ FAIL (−0.0154) |
| C2 improve ≥ +0.03 | ❌ FAIL |
| C3 engaged all | ✅ PASS |
| C4 promotion dual_pct | ❌ FAIL (เลือก cash; dual −0.0299) |

**คำตัดสิน**: ❌ **ไม่ผ่าน** — ลดความถี่ช่วย DD แต่ยังไม่ชนะ cash; E23 ยังเป็น
จูน dual ที่ดีที่สุดภายใต้ Line B; ห้ามเปลี่ยน default/gate

**ทำซ้ำ**: `python dual_conservative_demo.py`

---

## E24: Dual + separate short_cfg — v3.19, 2026-07-15

**คำถาม**: ถ้าจูน long/short คนละ geometry แบบ E11 ภายใต้ ExecutionProfile
จะชนะ cash บน held-out 4h และ promote ได้หรือไม่

**เกณฑ์ (ประกาศก่อนรัน)**: BTC/ETH/SOL × 4h; 60/40; ExecutionProfile;
`make_dual_layers(long, short_cfg=short)`; 60 iters × seeds 0/1/2;
เกณฑ์ C1–C4 เหมือน E23; ห้ามลด ValidationGate

**ผล** (`python dual_short_cfg_demo.py`):

| Dataset | untuned | tuned mean | delta |
|---|---|---|---|
| BTC 4h | -0.0479 | -0.0070 | +0.0410 |
| ETH 4h | -0.0188 | -0.0434 | −0.0246 |
| SOL 4h | -0.0472 | -0.0111 | +0.0361 |

Cross-asset tuned **−0.0205** vs untuned **−0.0380** (delta **+0.0175**)
— แย่กว่า E23 (−0.0078) โดยเฉพาะ ETH overfit ชัด

| Criterion | Result |
|---|---|
| C1 mean robust > 0 | ❌ FAIL (−0.0205) |
| C2 improve ≥ +0.03 | ❌ FAIL |
| C3 engaged all | ✅ PASS |
| C4 promotion dual_pct | ❌ FAIL (เลือก cash; dual −0.0083) |

**คำตัดสิน**: ❌ **ไม่ผ่าน** — แยก short_cfg ไม่แก้ negative_edge ภายใต้ Line B;
อย่าใช้เป็น default

**ทำซ้ำ**: `python dual_short_cfg_demo.py`

---

## E23: Tune dual_pct under Line-B costs — v3.19, 2026-07-11

**คำถาม**: ถ้าจูน geometry ของ dual stack ต่อสินทรัพย์ภายใต้ `ExecutionProfile`
(ไม่พึ่ง `require_edge`) จะชนะ cash บน held-out 4h และ promote ได้หรือไม่

**เกณฑ์ (ประกาศก่อนรัน)**: BTC/ETH/SOL × 4h; 60% train / 40% test;
`ExecutionProfile`; จูน `MemoryOrchestrator(make_dual_layers)` โดยตรง
60 iters × seeds 0/1/2; shared base; ผ่านรวมเมื่อ (1) mean robust test > 0
(2) improve ≥ +0.03 vs untuned (3) engaged ทุกสินทรัพย์ (4) promotion ด้วย
seed-0 params → eligible และ `selected_strategy==dual_pct` (gate เดิม)

**ผล** (`python dual_tune_demo.py`):

| Dataset | untuned robust | tuned mean (3 seeds) | delta | engaged |
|---|---|---|---|---|
| BTC 4h | -0.0479 | -0.0063 | +0.0416 | OK |
| ETH 4h | -0.0188 | -0.0033 | +0.0156 | OK |
| SOL 4h | -0.0472 | -0.0140 | +0.0332 | OK |

Cross-asset: tuned **−0.0078** vs untuned **−0.0380** (delta **+0.0301**)

| Criterion | Result |
|---|---|
| C1 mean robust > 0 | ❌ FAIL (−0.0078) |
| C2 improve ≥ +0.03 | ✅ PASS |
| C3 engaged all | ✅ PASS |
| C4 promotion dual_pct | ❌ FAIL (เลือก cash; dual −0.0181) |

**คำตัดสิน**: ❌ **ไม่ผ่าน** — จูนช่วยลดความเสียหายชัด (C2) และยังเทรดจริง (C3)
แต่ยังไม่ชนะ cash บน mean robust และไม่ promote; ห้ามเปลี่ยน production default;
ห้ามลดเกณฑ์ gate

**ทำซ้ำ**: `python dual_tune_demo.py`

---

## E22: Diagnose dual_pct vs cash — v3.18, 2026-07-11

**คำถาม**: ทำไม `dual_pct` แพ้ cash บน mean robust ข้าม BTC/ETH/SOL 4h (E21)
— เป็น DD, ไม่เทรด, หรือเทรดแล้วเสีย edge?

**เกณฑ์ (ประกาศก่อนรัน)**: protocol เดียวกับ E21; รายงาน ret/DD/robust/
TP/stop/rebuild/edge_skips ต่อสินทรัพย์; A/B `require_edge` OFF vs ON;
จัด primary mode เป็นหนึ่งใน drawdown_dominated / negative_edge_trading /
idle_no_trades / cost_drag; **ผ่านวินิจฉัย** เมื่อระบุ mode ได้และบันทึกซื่อๆ;
ไม่ใช่ promotion re-run; ห้ามลดเกณฑ์ gate

**ผล** (`python diagnose_dual_cash_demo.py`):

| Dataset | dual ret | dual DD | robust | TP | stop | rebuild | eskip |
|---|---|---|---|---|---|---|---|
| BTC 4h | -3.23% | 4.13% | -0.1149 | 274 | 84 | 40 | 0 |
| ETH 4h | -1.87% | 4.59% | -0.1104 | 309 | 78 | 39 | 0 |
| SOL 4h | -0.60% | 2.82% | -0.0625 | 298 | 70 | 44 | 0 |

Mean robust dual = **-0.0959** vs cash **0**. A/B `require_edge` ON≡OFF
(eskip=0 ทุกตลาด) → ไม่ใช่ cost_drag จาก spacing < round-trip

หมายเหตุ: regime_router มี return บวกบน ETH/SOL แต่ยังแพ้ cash บน robust
เพราะ 2×DD; dual แย่กว่าเพราะ return ติดลบทุกสินทรัพย์

**คำตัดสิน**: ✅ **วินิจฉัยผ่าน** — primary mode = **`negative_edge_trading`**
(เทรดจริงแล้วเสีย; ไม่ idle; edge filter ไม่ช่วยภายใต้ params ปัจจุบัน)
ไม่ promote; ไม่เปลี่ยน default `require_edge`

**ทำซ้ำ**: `python diagnose_dual_cash_demo.py`

---

## E21: Dual+Percentile Promotion Gate (Line B) — v3.17, 2026-07-11

**คำถาม**: ถ้าใส่ dual 75/25 + percentile (`dual_pct`) เป็น candidate ในสาย B
research/core แล้วรัน promotion gate ข้าม BTC/ETH/SOL 4h จะได้
`eligible_for_paper` และเลือก `dual_pct` หรือไม่

**เกณฑ์ (ประกาศก่อนรัน)**: candidates = cash + buy_hold + regime_router +
regime_allocator + **dual_pct**; `ExecutionProfile` ต้นทุนจริง;
`use_regime_pct=True`; ไม่มี RL/funding/relative; ValidationGate เดิม
(median_test_score ≥ 0, failure_rate ≤ 50%, folds ≥ 3) ต้องผ่าน**ทุก** dataset;
**ผ่านรวม** ก็ต่อเมื่อ `eligible_for_paper=True` และ
`selected_strategy == "dual_pct"`

**ผล** (`python promotion_dual_demo.py`):

| Dataset | median OOS | failure | folds | gate |
|---|---|---|---|---|
| BTCUSDT 4h | +0.0000 | 0.0% | 14 | PASS |
| ETHUSDT 4h | +0.0000 | 28.6% | 14 | PASS |
| SOLUSDT 4h | +0.0000 | 14.3% | 14 | PASS |

Leaderboard (mean return − 2×maxDD): cash +0.0000 > regime_allocator −0.0909 >
regime_router −0.0910 > dual_pct −0.0959 > buy_hold −1.8532

Selected: **cash** · Paper eligible: **False** · Core → cash

**คำตัดสิน**: ❌ **ไม่ผ่าน** — gate ผ่านทุก dataset แต่ leaderboard เลือก cash
(benchmark) จึงไม่ eligible; `dual_pct` ยังแพ้ cash บน robust score ข้าม 3 สินทรัพย์
Wiring ถือว่าเสร็จ (`dual_pct` ใน `default_strategies` + `CoreTradingEngine._ALLOWED`)

**ทำซ้ำ**: `python promotion_dual_demo.py`

---

## E20: Walk-Forward RL — v3.16, 2026-07-11

**คำถาม**: ผล E19 (dual RL ชนะ dual rule บน BTC/4h held-out หน้าต่างเดียว)
ทนต่อการเลื่อนเวลาแบบ rolling walk-forward หรือไม่

**เกณฑ์ (ประกาศก่อนรัน)**: ต่อ fold = WIN ถ้า RL robust > rule และ
`n_scale_changes > 0`; นับเฉพาะ engaged folds; ผ่านรวมก็ต่อเมื่อ win rate
**> 50%** และ engaged folds **≥ 3**

**Protocol**: BTC/4h, train=800 / test=200 / step=200 → 6 folds; ต่อ fold
tune → `train_q_on_ohlc` (epochs=6, seeds 0/1/2) → dual rule vs RL;
`use_regime_pct=True`; ห้ามโหลด Q เก่า

**ผล** (`python rl_walkforward_demo.py`):

| Fold | Train | Test | rule robust | RL robust | chg | Win |
|---|---|---|---|---|---|---|
| 0 | 0-800 | 800-1000 | +0.0008 | **+0.0019** | 2 | YES |
| 1 | 200-1000 | 1000-1200 | -0.0198 | -0.0198 | 2 | no |
| 2 | 400-1200 | 1200-1400 | -0.0006 | -0.0006 | 2 | no |
| 3 | 600-1400 | 1400-1600 | -0.0543 | **-0.0538** | 2 | YES |
| 4 | 800-1600 | 1600-1800 | -0.0625 | -0.0654 | 1 | no |
| 5 | 1000-1800 | 1800-2000 | -0.0019 | **-0.0017** | 1 | YES |

Engaged win rate: **3/6 (50%)**

**คำตัดสิน**: ❌ **ไม่ผ่าน** — มี ≥3 engaged แต่ win rate = 50% ไม่เกินเกณฑ์
ที่ประกาศ (>50%). E19 หน้าต่างเดียว**ไม่ยืนยัน**ภายใต้ walk-forward —
RL บนข้อมูลจริงยังไม่เสถียรพอจะแนะนำแม้บน BTC/4h  
คงนโยบาย: ห้ามใช้ RL เป็น default; Q synthetic ยังห้าม; E19 เป็นหลักฐานอ่อน

**ทำซ้ำ**: `python rl_walkforward_demo.py`

---

## E19: RL Retrain on Real Data — v3.15, 2026-07-11

**คำถาม**: ถ้า retrain Q-table บน BTC/4h จริงเท่านั้น (ห้ามใช้ Q synthetic)
พร้อม state จาก `use_regime_pct` (แก้สเกลตาม E12) จะชนะ dual rule บน
held-out test ได้ไหม

**เกณฑ์ (ประกาศก่อนรัน)**:
- **Primary**: dual RL `robust = return - 2*maxDD` **สูงกว่า** dual rule บน
  BTC/4h test 40% และ `n_scale_changes > 0`
- **Secondary (รายงานอย่างเดียว)**: Q เดียวกันบน bull 1d vs dual rule —
  ไม่เปลี่ยนคำตัดสิน

**Protocol**: tune params บน train 60%; `train_q_on_ohlc` 8 epochs × seeds
(0,1,2); dual 75/25; percentile regime; ไม่โหลด `q_table*.json` เก่า; บันทึก
audit ที่ `results/q_table_real_e19.json`

**ผล** (`python rl_real_demo.py`):

| สนาม | dual rule robust | dual RL robust | ผล |
|---|---|---|---|
| **BTC/4h held-out (primary)** | -0.0017 | **-0.0015** (scale_changes=6) | **PASS** |
| Bull 1d secondary | -0.0150 | -0.0161 (scale_changes=11) | RL แพ้ — transfer ข้าม TF ยังอ่อน |

**คำตัดสิน**: ✅ **ผ่านเกณฑ์ primary ที่ประกาศ** — RL ที่ train บนข้อมูลจริง +
percentile state ชนะ dual rule บน held-out BTC/4h เดียวกัน  
⚖️ Secondary ยืนยันว่า **ห้ามย้าย Q ข้าม timeframe** (bull 1d ยังแพ้ rule)  
ยัง **ไม่ใช่คำแนะนำเทรดจริง** — ใช้ได้เฉพาะ Q ที่ train+held-out บนตลาด/TF
เดียวกัน; ห้ามใช้ Q จาก synthetic

**ทำซ้ำ**:
```
python -m unittest tests.test_strategy_framework
python rl_real_demo.py
```

---

## E18: Cross-Asset Relative-Value — v3.14, 2026-07-11

**คำถาม**: ถ้าใช้ momentum ของอัตราส่วน alt/BTC (percentile-rank) **แทน**
direction จาก regime ราคาเดี่ยว จะลด DD โดยไม่ทำลาย return บน ETH/SOL 4h ได้ไหม

**เกณฑ์ (ประกาศก่อนรัน)**: engaged pass rate **> 50%** — pass ต่อ seed =
ON ลด maxDD และไม่ทำลาย return (กฎ E13); นับเฉพาะ engaged
(`n_relative_tilts > 0` หรือผลต่างจาก OFF)

**Protocol**: ETH/SOL × 4h, BTC เป็น numeraire, ต้นทุนจริงแบบ E13, tune train 60%
ด้วย relative OFF, ทดสอบ 40%, 3 seeds; funding bias ปิดทั้งคู่; ON ใช้
`pair_ratio_series` momentum แทน own-price direction

**ผล** (`python relative_value_demo.py`):

| Market | Engaged | Pass |
|---|---|---|
| ETH/4h | 3/3 | **0/3** (ON เพิ่ม DD ทุก seed) |
| SOL/4h | 3/3 | **2/3** |
| **รวม** | 6/6 | **2/6 (33%)** |

Tilts ~459–476 ต่อ test window — กลไกแทน direction จริงทุก seed

**คำตัดสิน**: ❌ **ไม่ผ่านเกณฑ์ (>50%)** — relative-value engage ได้แต่โดยรวม
เพิ่ม drawdown (โดยเฉพาะ ETH). Default `use_relative_value=False` คงไว้
ห้ามเปิดเป็นค่าเริ่มต้น; บันทึกผลลบเท่าผลบวก

**ทำซ้ำ**:
```
python -m unittest tests.test_strategy_framework
python relative_value_demo.py
```

---

## E17: Funding-Rate Directional Bias — v3.13, 2026-07-11

**คำถาม**: ถ้าใช้ funding rate จริงแบบ percentile-rank เป็น directional bias
(สุดขั้วบวก = overcrowd long → เอียง short; สุดขั้วลบ → เอียง long) เฉพาะตอน
regime sideways จะลด DD โดยไม่ทำลาย return บน 4h จริงได้ไหม

**เกณฑ์ (ประกาศก่อนรัน)**: engaged pass rate **> 50%** — pass ต่อ seed =
ON ลด maxDD และไม่ทำลาย return (กฎแบบ E13); นับเฉพาะ runs ที่ engage
(`n_funding_tilts > 0` หรือผลต่างจาก OFF)

**Protocol**: BTC/ETH/SOL × 4h, ต้นทุนจริง (fee+CS-spread+mean funding cost),
tune train 60% ด้วย bias OFF, ทดสอบ 40%, 3 seeds; ทั้งคู่ใช้ percentile regime
router — ต่างกันแค่ `use_funding_bias`

**ผล** (`python funding_bias_demo.py`):

| Market | Engaged | Pass |
|---|---|---|
| BTC/4h | 3/3 | **0/3** (ON แย่ลงทั้ง ret และ DD) |
| ETH/4h | 3/3 | **0/3** |
| SOL/4h | 3/3 | **3/3** (DD ลด + ret ไม่แย่ลง) |
| **รวม** | 9/9 | **3/9 (33%)** |

Tilts ต่อ test window: BTC~112, ETH~103, SOL~93 — กลไก engage จริงทุก seed

**คำตัดสิน**: ❌ **ไม่ผ่านเกณฑ์ที่ประกาศ (>50%)** — funding bias ทำงานและ engage
ได้ แต่โดยรวมทำลายผลบน BTC/ETH; ช่วยเฉพาะ SOL/4h ภายใต้ protocol นี้
Default `use_funding_bias=False` คงไว้ — **ห้ามเปิดเป็นค่าเริ่มต้น**
บันทึกผลลบเท่าผลบวก; ไม่ claim พร้อมใช้งาน

**ทำซ้ำ**:
```
python -m unittest tests.test_strategy_framework
python funding_bias_demo.py
```

---

## E16: Edge Filter Before Build — v3.12, 2026-07-11

**คำถาม**: ถ้าปฏิเสธการสร้างโซนเมื่อ `tp_mult * spacing / price` ไม่คุ้ม
round-trip `2*fee_rate + 2*half_spread` จะกัน negative-EV ได้ไหม และอธิบาย
SOL/4h ใน E13/E14 ได้หรือไม่

**เกณฑ์ (ประกาศก่อนรัน)**:
1. Unit: `require_edge=True` + costs สูงกว่า TP → `center is None`, `n_edge_skips >= 1`;
   costs ต่ำ → สร้างโซน; default `require_edge=False` ไม่เปลี่ยนพฤติกรรมเดิม
2. Mechanism บน SOL/4h จริงด้วย spacing บางโดยเจตนา (`atr_mult=0.15`) ต้องได้
   `n_edge_skips > 0`
3. Diagnostic (ไม่ใช่ pass gate): รายงาน E13-tuned SOL/4h + BTC/4h ว่าสมมติฐาน
   "spacing < ต้นทุน" ถือกับ tuned params หรือไม่ — ห้าม claim ว่า SOL เริ่มกำไร

**Protocol**: helpers `round_trip_cost_frac` / `has_positive_edge`; flag
`require_edge` (default off) ใน long+short `_build`; `ExecutionProfile` ใส่
`half_spread` จาก dataset; demo `edge_filter_demo.py`

**ผล**:
| เคส | ผล |
|---|---|
| Unit (13 tests incl. edge) | PASS |
| Thin SOL/4h `atr_mult=0.15` | **PASS** — edge_skips=787, rebuilds=0, rt=76.9bps vs tp~=22bps |
| E13-tuned SOL/4h | edge_skips=0, 1 TP, tp~=2084bps >> rt 77bps — **สมมติฐานไม่ยืนยัน** |
| E13-tuned BTC/4h | edge_skips=0, 4 TPs, tp~=301bps > rt 48bps |

**คำตัดสิน**: ✅ **กลไก edge filter ผ่านเกณฑ์ 1–2** — ปฏิเสธโซน negative-EV ได้จริง
เมื่อเปิด `require_edge`. ⚖️ สมมติฐานเดิมที่ว่า SOL/4h ใน E13/E14 ไม่เทรดเพราะ
spacing < ต้นทุน **ไม่รองรับด้วย tuned params** — ค่า n/a ของ SOL/4h คือ OFF==ON
(router ไม่เปลี่ยนผล) และยังมี fills น้อย (0–1 TP) แต่ spacing ที่ tune แล้วกว้างพอ
ชัดเจน Default ยังเป็น `require_edge=False` เพื่อไม่พัง legacy

**ทำซ้ำ**:
```
python -m unittest tests.test_strategy_framework
python edge_filter_demo.py
```

---

## E15: Line-B Percentile Integration — v3.11, 2026-07-11

**คำถาม**: ถ้าเชื่อม `PercentileRegimeDetector` (สาย A / E14) เข้าสาย B
(`RegimeSignalModel` → `RegimeSwitchingOrchestrator` → research/core) แทน
fixed-threshold ที่ hardcode อยู่ แล้วรัน purged-CV promotion gate ของ framework
ใหม่ซ้ำ — ผล gate จะต่างจาก fixed-threshold แค่ไหน?

**เกณฑ์ (ประกาศก่อนรัน)**: นี่คือการวัดผล integration ไม่ใช่เกณฑ์ promote-to-paper
- รายงาน PASS/FAIL + median OOS ของ **ทั้งสอง** detector บน protocol เดียวกัน
- ห้าม cherry-pick และห้าม claim "พร้อมเทรดจริง" จากผลนี้
- Integration สำเร็จถ้า: (a) router สร้าง `PercentileRegimeDetector` เมื่อ
  `use_regime_pct=True` และ (b) demos รันจบโดยไม่พัง

**Protocol**:
1. Wire: `RegimeSignalModel(cfg=...)` → `build_detector(cfg)`;
   `CoreTradingEngine` default `use_regime_pct=True`
2. A/B บน BTCUSDT 4h: `strategy_gate_demo.py` — fixed (`use_regime_2d`) vs pct
   (`use_regime_pct`), candidates = fixed_router vs allocated_router,
   `combinatorial_purged_screen(n_groups=6, n_test_groups=2, purge_groups=1)`
3. Cross-asset: `multi_strategy_research_demo.py` ด้วย pct
4. Edge A/B: `regime_switch_edge_demo.py` ด้วย pct ใน REALISTIC

**ผล**:

| Detector | Gate | Median OOS | Selection failure |
|---|---|---|---|
| Fixed-threshold (`use_regime_2d`) | FAIL | -0.0539 | 57.1% |
| Percentile-rank (`use_regime_pct`) | FAIL | -0.0723 | **42.9%** |

Cross-asset research (pct): leaderboard เลือก **cash**; paper eligible = False
(benchmark ไม่ใช่ tradable). Core engine fail-closed → cash / +0.00%.

`regime_switch_edge_demo` (pct): synthetic MEAN robust regime-switch **-0.0189**
ดีกว่า fixed-75/25 (-0.0272) และ long-only (-0.0229); real bear 2022 regime-switch
robust **-0.0681** ดีที่สุดในสามตัว; real bull 2023-2026 regime-switch **-0.3468**
แย่กว่า fixed-75/25 (-0.2619) — ไม่ claim ชนะทุกสนาม

**คำตัดสิน**: ⚖️ **Integration gap ปิดแล้ว** — สาย B ใช้ `build_detector` /
`use_regime_pct` เหมือนสาย A. Promotion gate ของ framework **ยัง FAIL ทั้งคู่**
(cash-default ถูกต้อง). Percentile ลด selection failure 57.1%→42.9% แต่ median OOS
ยังติดลบและแย่กว่า fixed เล็กน้อยบน BTC 4h gate นี้ — **ไม่ใช่หลักฐานว่าพร้อม paper**
และไม่ขัดกับ E14 (E14 วัด relative pass rate ข้ามสินทรัพย์คนละ protocol)

**ทำซ้ำ**:
```
python -m unittest tests.test_strategy_framework
python strategy_gate_demo.py
python multi_strategy_research_demo.py
python core_engine_demo.py
python regime_switch_edge_demo.py
```

---

## E14: Percentile-Rank Regime — v3.10, 2026-07-11

**คำถาม**: ถ้าเปลี่ยนจาก fixed-threshold (`m_threshold`, `vol_hi` คงที่) เป็น
**percentile-rank ของ momentum/vol_ratio เทียบ rolling distribution ของตัวเอง**
(scale-invariant โดยธรรมชาติ) จะแก้ปัญหาที่ E13 เจอได้ไหม — เพราะ root cause ของ E13
คือ 1 threshold คู่เดียวใช้กับทั้ง BTC และ SOL, ทั้ง 1d และ 4h ไม่ได้ (สเกล momentum/vol_ratio
ต่างกันคนละระดับ) ปัญหาเดียวกับที่พบใน E8 (config ไม่ transfer ข้าม volatility scale) และ
E12 (RL state signal จำแนกผิดข้ามสเกล)

**เกณฑ์ (ประกาศก่อนรัน)**: percentile-rank router คุ้มค่าใช้แทนก็ต่อเมื่อ pass rate
**สูงกว่าอย่างชัดเจน** เทียบ fixed-threshold ของ E13 — วัดด้วย protocol เดียวกันเป๊ะ
(ห้ามเปลี่ยนอะไรนอกจากตัว detector เพื่อไม่ให้เทียบเพี้ยน)

**Protocol**: เหมือน E13 ทุกประการ (6 ตลาด BTC/ETH/SOL × 1d/4h, ต้นทุนจริงชุดเดียวกัน,
จูน train 60% ด้วย router OFF, ทดสอบ 40% หลัง, 3 seeds/ตลาด, กฎ pass เดียวกัน) เพิ่มแค่
`PercentileRegimeDetector` เป็น variant ที่ 3: จำแนก regime จาก percentile rank ของค่า
momentum/vol_ratio ปัจจุบันเทียบ **trailing window ของตัวเอง** (default 250 แท่ง, เกณฑ์
percentile 85) แทนการเทียบ constant คงที่ — ใช้ confirm/dwell/hysteresis เดิมจาก
PersistentRegimeDetector ทุกอย่าง เปลี่ยนแค่ขั้นตอนจำแนก raw signal

**ผล** (`results/percentile_regime_e14.csv`):

| | Fixed-threshold (E13) | **Percentile-rank (E14)** |
|---|---|---|
| Pass rate (engaged runs) | 6/14 (43%) | **10/12 (83%)** |
| BTC/1d | 1/3 | **3/3** |
| BTC/4h | 2/3 | **3/3** |
| ETH/1d | 1/2 | 0/2 engaged (ผล unchanged จาก OFF ใน 2 seeds) |
| ETH/4h | 1/3 | **3/3** |
| SOL/1d | 1/3 | 1/3 (เท่าเดิม แต่ seed ที่ผ่านเป็นคนละ seed) |
| SOL/4h | n/a | n/a (ไม่เทรดเหมือนเดิม — ต้นทุนสูงกว่า spacing) |

**คำตัดสิน**: ✅ **ผ่านเกณฑ์ที่ประกาศไว้ — pass rate เพิ่มขึ้นเกือบเท่าตัว (43%→83%)**
ด้วย protocol เดียวกันเป๊ะ ไม่มีการเปลี่ยนกฎหรือเลือกเกณฑ์ทีหลัง — **percentile-rank
regime detector กลายเป็นตัวเลือกที่แนะนำแทน fixed-threshold** สำหรับ regime router

**ข้อสังเกตที่ต้องรายงานตรงๆ (ไม่ใช่แค่ข่าวดี)**:
1. BTC/1d "ผ่าน" ทุก seed แต่ DD สัมบูรณ์ยังสูง (15-20%) — แปลว่า "ผ่าน" ตามกฎ
   (ดีขึ้นกว่า baseline) ไม่ได้แปลว่า "ปลอดภัยพอใช้งานจริง" ต้องแยกสองคำถามนี้ออกจากกัน
2. ETH/1d กลับแย่ลงเล็กน้อย (จาก engaged 1/2 เป็น engaged 0/2 คือ router ไม่ทำอะไรเลย
   ในตลาดนี้แทนที่จะช่วย) — percentile-rank ไม่ใช่ยาวิเศษทุกกรณี
3. SOL/4h ยังไม่เทรดเหมือนเดิม — ปัญหา "ต้นทุนกด edge filter" ที่ตั้งข้อสังเกตไว้ตั้งแต่
   E13 ยังไม่ถูกแก้ (เป็นแนวทางที่ 3 ที่ยังไม่ได้ทดสอบ — "edge filter ก่อนเข้า")

**ทำซ้ำ**: `python percentile_regime_demo.py` (ใช้ `dynamic_grid/regime.py`:
`PercentileRegimeDetector`, `build_detector()`; config flags `use_regime_pct`,
`regime_pct_window`, `regime_trend_pct`, `regime_vol_pct`)

---

## E13 (ล่าสุด): Cross-Asset Regime-Router Validation — v3.9, 2026-07-11

**คำถาม**: regime router (PersistentRegimeDetector 2D + confirm/dwell/hysteresis +
block_high_vol_entries) ลด drawdown โดยไม่ทำลายผลตอบแทน **ข้ามสินทรัพย์** บนข้อมูลจริง
พร้อมต้นทุนจริงหรือไม่

**เกณฑ์ (ประกาศโดยผู้ใช้ก่อนรัน)**: ต้องลด DD โดยไม่ทำลาย return ข้ามสินทรัพย์
จึงจะถือว่า defensive edge เริ่มมีหลักฐานรองรับ

**Protocol**:
- 6 ตลาด: BTC/ETH/SOL × 1d (1000 แท่ง ~2.7 ปี) / 4h (2000 แท่ง ~11 เดือน) — Binance spot จริง
- ต้นทุน: fee 0.05%/ข้าง + half-spread (Corwin-Schultz จาก high/low จริง) +
  **funding history จริง 500 events/เหรียญ** (BTC +0.00084%/8h, ETH ~0, SOL **-0.00366%/8h**
  — long ได้เงิน, texture ที่ synthetic ไม่มี)
- จูน 60% train โดย router **ปิด** (กันจูนเข้าข้าง router) → ทดสอบ 40% หลัง OFF vs ON
- **3 seeds ต่อตลาด** (มาตรฐานจากบทเรียน E7) — ตัดสินเฉพาะ runs ที่ router "engage" จริง
- Volume check: max exposure ~0.001% ของ median bar quote volume → ไม่ต้องมี impact model

**ผล** (ดิบเต็มที่ `results/multiasset_router_validation.csv`):

| ตลาด | ผ่าน/engaged seeds | ข้อสังเกต |
|---|---|---|
| BTC/1d | 1/3 | ทิศทางไม่คงที่ระหว่าง seed |
| BTC/4h | **2/3** | ดีสุดในกลุ่ม |
| ETH/1d | 1/2 | 1 run ไม่ engage |
| ETH/4h | 1/3 | |
| SOL/1d | 1/3 | สุดขั้ว: seed 0 router เพิ่ม loss เท่าตัว (-10%→-18.5%), seed 2 เกือบล้าง loss (-5.3%→-0.03%) |
| SOL/4h | 0 engaged | แทบไม่เทรดใต้ต้นทุนที่ประมาณไว้ |

**คำตัดสิน**: ❌ **ไม่ผ่าน — 6/14 engaged runs (43%), ไม่มีตลาดที่ผ่านทุก seed,
ผลของ router เล็กกว่า noise ของ seed การจูน** → defensive edge ยังไม่มีหลักฐานรองรับ
ข้ามสินทรัพย์ ณ วันนี้

**ข้อจำกัดของการทดลอง**:
1. CS spread estimate สูงกว่า spread จริงของ Binance มาก (1d: 0.57–1.12%/ข้าง vs จริง
   ~0.01–0.05%) — ยุติธรรมภายใน (ON/OFF ต้นทุนเดียวกัน) แต่กดจำนวนเทรดจน 4/18 runs
   router ไม่ engage
2. Funding ใช้ค่าเฉลี่ยคงที่จาก 500 events (~167 วัน) ไม่ time-varying
3. Test window เดียวต่อตลาด (40% ท้าย) — ยังไม่ multi-window

**เงื่อนไขก่อนทดสอบซ้ำ**: L1 spread จริง, จูน confirm/dwell แยกต่อ timeframe,
seeds + test windows มากขึ้น, ลดมิติการจูนฐาน

**ทำซ้ำ**: `python multiasset_demo.py` (data: `data/{BTC,ETH,SOL}USDT_{1d,4h}.json`,
`data/*_funding.json`)

---

## E12: RL Reality-Check — v3.8, 2026-07-09

**คำถาม**: RL governor (ชนะทุกตัวบน synthetic) + dual portfolio = edge จริงหรือไม่
**เกณฑ์**: robust score (return − 2×maxDD) บน 3 สนาม: synthetic held-out / bear จริง / bull จริง
**ผล**: ชนะ synthetic (-0.0164 ดีสุดใน 4 variants) และ bear จริง (-0.0895 ดีสุด) แต่
**bull จริง: RL พลิกกำไรเป็นขาดทุน** — long rule +5.50% → long RL **-2.72%**;
dual rule +3.91% → dual RL **-1.88%**
**คำตัดสิน**: ❌ ถอนคำแนะนำ RL ทุก variant — สาเหตุ: policy เรียน state จาก synthetic
dynamics (ATR ~0.8%/แท่ง) จำแนกผิดบน BTC จริง (~5%/แท่ง) | **นโยบายใหม่: ผล RL ต้องผ่าน
held-out บนข้อมูลจริงเท่านั้น synthetic benchmark ไม่พอ**
**ทำซ้ำ**: `python edge_demo.py`

## E11: Dual-Side Portfolio — v3.7, 2026-07-09

**เกณฑ์**: robust score, 3 สนาม, น้ำหนัก 75/25 ประกาศก่อน ไม่ sweep
**ผล**: dual ชนะ long-only ทั้ง 3 สนาม — synthetic -0.0309 vs -0.0342; bear จริง
-1.99%/DD 3.63% vs -3.21%/DD 5.46%; bull จริง robust -0.1234 vs -0.1639 (return ดิบแพ้
+3.91% vs +5.50% — ชนะเพราะกด DD)
**คำตัดสิน**: ✅ **Dual Rule-based คือ config แนะนำปัจจุบัน** — ตัวเดียวที่ transfer
สม่ำเสมอทั้ง bear/bull จริง | **ทำซ้ำ**: `python dual_demo.py`

## E9-E10: Short Grid + RL บน synthetic — v3.6, 2026-07-09

E9 **Short บน bear จริง** (จูนเฉพาะปี 2021 ที่เป็นขาขึ้น → ทดสอบ 2022 unseen, 3 seeds):
SHORT +0.63%/DD 0.54% ขณะ LONG -3.94%/DD 8.83% → ✅ ถูกทิศ ปลอดภัย เป็นบวกในตลาดที่
long เสียหาย (⚠️ ยังไม่รวม funding) | **ทำซ้ำ**: `python bear_short_demo.py`

E10 **RL synthetic**: robust -0.0230 vs rule -0.0342 vs fixed -0.0383 → ✅ บน synthetic
(ภายหลังถูกหักล้างด้วย E12 บนข้อมูลจริง — ดูบทเรียน)

## E8: Volatility-Scale Transfer — v3.6, 2026-07-09

Config จูนบน synthetic (ราคา 100, vol ~0.8%/แท่ง) วางบน BTC จริง (~5%/แท่ง):
zone ลึกเกิน 100% — levels ราคาติดลบถึง -22k, stop -27k ไม่มีวัน trigger, แทบไม่เทรด
โดยไม่มี error เตือน → ❌ **ห้าม transfer config ข้าม volatility scale — ต้อง re-tune
บนข้อมูล scale เป้าหมายเสมอ**

## E6-E7: Walk-Forward ข้อมูลจริงครั้งแรก — v3.2/v3.2.1, 2026-07-08

E6: train 250d → test 60d unseen × 12 folds บน BTC 2023-26: **Static ชนะ Dynamic ทุก
ตัวชี้วัด** (mean +2.76% vs +0.76%) — optimizer overfit ต่อ regime ของ train window เดียว
→ ❌ synthetic backtest ไม่ใช่หลักฐานของความเหนือกว่าบนตลาดจริง

E7: sub-window robust scoring แก้บางส่วน — worst DD ของ Static 21.47%→3.56% แต่ Static
ยังชนะ mean/median return | **บทเรียนสำคัญ: ผลรอบแรกที่ดูดีมาจาก seed เดียว — ต้อง
aggregate หลาย seeds เสมอ** (มาตรฐานที่ใช้ในทุกการทดลองหลังจากนั้น)
**ทำซ้ำ**: `python walk_forward_demo.py`

## E1-E5: รากฐาน synthetic — v1→v3.1, 2026-07-06/07

- E1: Dynamic แก้ "โดนลาก" ได้จริง — downtrend DD 77%→5% (จุดขายหลัก พิสูจน์บน synthetic)
- E2: regime module ผ่าน held-out (+0.50% vs +0.28% mean return)
- E3: จูน regime แรงเกิน → held-out return พัง (+0.12%) — กำเนิดกฎ "ต้องมี held-out เสมอ"
- E4: multi-layer ลด DD 12-20% ทุกตลาด แลก return ~ครึ่ง — trade-off ตามปรัชญา
- E5: momentum confirm ชนะบน robust score ที่ประกาศก่อน (แพ้ถ้าวัด return) — กำเนิดกฎ
  "เกณฑ์ต้องประกาศก่อนทดลอง"

---

## แนวทางที่ยังไม่ได้ทดสอบ (candidate สำหรับ E24+)

1. ~~**Edge filter**~~ E16 / ~~**Funding**~~ E17 fail / ~~**Relative**~~ E18 fail
2. ~~**RL บนข้อมูลจริง**~~ E19 primary ผ่าน แต่ ~~**walk-forward**~~ E20 **ไม่ผ่าน** (3/6=50%)
3. ~~**Promotion gate สาย B ด้วย dual+pct**~~ E21: wiring เสร็จ แต่เลือก cash
4. ~~**วินิจฉัย dual vs cash**~~ E22: **`negative_edge_trading`**
5. ~~**จูน dual ภายใต้ ExecutionProfile**~~ E23: ดีขึ้น (+0.03) แต่ยังแพ้ cash / ไม่ promote
6. Candidates ถัดไป: แยก `short_cfg` แบบ E11; หรือลดความถี่เทรด/DD เพิ่มจน robust > 0
   ก่อน promote; หรือ RL ที่เปลี่ยน reward/state แล้ว walk-forward ใหม่
   (ห้ามลดเกณฑ์หลังเห็นผล)

## กฎเหล็กที่กลั่นจากทุกการทดลอง (ใช้บังคับกับการทดลองถัดไป)

1. **ประกาศเกณฑ์ก่อนรัน** — เลือกเกณฑ์หลังเห็นผล = โกงตัวเอง (E5)
2. **Held-out เสมอ** — in-sample ดีแค่ไหนก็เชื่อไม่ได้ (E3)
3. **หลาย seeds เสมอ** — seed เดียวที่ดูดีคือความบังเอิญ (E7, E13)
4. **Synthetic พิสูจน์แค่ "กลไกทำงาน"** — ไม่ใช่หลักฐานผลกำไรบนตลาดจริง (E6, E12)
5. **ห้าม transfer config/policy ข้าม volatility scale** (E8, E12)
6. **ผลลบมีค่ากว่าผลบวก** — บันทึกทุกความล้มเหลวลง ledger นี้และ knowledge graph
7. **RL ต้อง validate บนข้อมูลจริงเท่านั้น** (E12)
8. **นับเฉพาะ runs ที่กลไก engage จริง** — ON==OFF ไม่ใช่หลักฐานว่าดีหรือแย่ (E13)

> สถานะรวม ณ 2026-07-11: **ระบบยังไม่พร้อมเทรดเงินจริง** — E23 ยืนยันว่าจูน dual
> ภายใต้ต้นทุนจริงช่วยได้ (+0.03 robust) แต่ยังแพ้ cash (−0.0078) และไม่ promote.
> สาย B ยัง fail-closed เป็น cash ถูกต้อง. อย่าใช้ RL เป็น default (E20).
> ห้ามลดเกณฑ์ ValidationGate
