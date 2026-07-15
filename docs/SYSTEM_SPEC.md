# เอกสารระบบ Dynamic Grid Trading System (v3.10 — Percentile-Rank Regime)

> ⚠️ **อ่านหัวข้อ 15.5 และ 15.7 ก่อนอ่านส่วนอื่น** — RL Governor ที่ train บน synthetic
> เพียงอย่างเดียว **พลิกกำไรเป็นขาดทุนบนตลาดกระทิงจริง** (+5.50%→-2.72%) แม้จะชนะบน synthetic
> benchmark ทุกตัว — **ห้ามใช้ RL variant ใดๆ เทรดเงินจริง** | v3.10 แก้ regime router ด้วย
> percentile-rank (แทน fixed threshold) — pass rate cross-asset เพิ่ม 43%→83% (หัวข้อ 15.7)
> ใช้ **Dual Rule-based + Percentile-rank regime** เป็น config แนะนำปัจจุบัน ซึ่งเป็น
> ตัวเดียวที่ transfer ไปข้อมูลจริงได้สม่ำเสมอทั้ง bear/bull — Static Grid ยังชนะ Dynamic บน
> BTC จริงในบางกรอบเวลาด้วย (หัวข้อ 13) **ทั้งระบบยังไม่ควรใช้เทรดเงินจริงโดยตรง**

> ฉบับวันที่ 8 กรกฎาคม 2026 | สถานะ: ต้นแบบเพื่อการวิจัย

---

## 1. ปรัชญาการออกแบบ

หัวใจของระบบไม่ใช่การทำกำไรสูงสุดในทุกสถานการณ์ แต่คือ **"ปรับตัวและบริหารความเสี่ยง"**
เพื่อให้อยู่รอดได้ในทุกสภาวะตลาด (Robustness ก่อน Return) โดยแก้จุดตายของ
Linear Grid แบบดั้งเดิม 3 จุด:

| จุดตายของ Linear Grid | วิธีแก้ในระบบนี้ |
|---|---|
| ระยะกริดคงที่ ไม่รู้จัก volatility | Order distance = `atr_mult × ATR` ณ เวลาสร้างโซน |
| โดนลาก/ติดดอยเมื่อเจอเทรนด์แรง (DD 80–90%) | Zone stop + Cooldown + Trend filter + Regime gate |
| Order Clustering แบบไร้เพดานความเสี่ยง | Risk per Zone: ขาดทุน worst-case ต่อโซนถูก cap ล่วงหน้า |

หลักฐานเชิงประจักษ์ (synthetic downtrend, 2,000 แท่ง): Static grid −76% / DD 77%
ในขณะที่ Dynamic grid (จูนแล้ว) ประมาณ −5% / DD ~5–7%

---

## 2. สถาปัตยกรรม

```
dynamic_grid/
  indicators.py    ATR (Wilder) + AnomalyDetector
  regime.py        RegimeDetector (v2) — จำแนกสภาวะตลาด 4 โหมด
  risk.py          Position sizing แบบ Risk per Zone
  grid_engine.py   DynamicGridEngine (ระบบหลัก) + StaticGridEngine (baseline)
  orchestrator.py  MultiLayerOrchestrator (v3) — คุม N layer ที่คนละสเกลราคา
  synthetic.py     เครื่องกำเนิดข้อมูล 6 แบบจำลอง
  backtest.py      Backtester รายแท่ง + metrics (รองรับทั้ง engine เดี่ยวและ orchestrator)
  optimize.py      Random-search optimizer แบบ robust ข้ามหลายตลาด
run_demo.py          เดโม: เทียบ Static vs Dynamic + optimize
compare_versions.py  Ablation test: v1 (ไม่มี regime) vs v2 (มี regime)
multilayer_demo.py   เดโม: เทียบ Single-layer vs Multi-Layer (v3)
```

การไหลของข้อมูลต่อ 1 แท่ง (OHLC):

```
bar ─► ATR ─► AnomalyDetector ─► RegimeDetector ─► GridEngine.on_bar()
                                                        │
                       ┌────────────────────────────────┤
                       ▼                                ▼
                 realized PnL ──► Backtester ──► equity curve / metrics
```

---

## 3. Regime Detection (v2)

จำแนกตลาดด้วย 2 สัญญาณ (streaming, ไม่มี lookahead):

- **Momentum**: `m = (EMA20 − EMA60) / ATR_slow` — ทิศทางและความชัน normalize ด้วย vol
- **Vol ratio**: `v = ATR10 / ATR50` — ความผันผวนกำลังเร่งหรือสงบ

| เงื่อนไข | Regime | ผลต่อการสร้างโซน |
|---|---|---|
| `v > regime_vol_hi` | `high_vol` | risk × `hv_risk_scale` (ไม้เล็กลง), spacing × `hv_spacing_scale` (กริดถ่าง) |
| `m > m_threshold` | `trend_up` | risk × `up_risk_scale` (เพิ่ม budget เล็กน้อย) |
| `m < −m_threshold` | `trend_down` | **ห้ามสร้างโซนใหม่** (ไม่วางกริดสวนขาลงที่ยืนยันแล้ว) |
| อื่นๆ | `sideways` | ค่าปกติ |

การปรับเกิด ณ **เวลาสร้างโซนเท่านั้น** (ไม่แกว่งรายแท่ง) — โซนที่เปิดอยู่ใช้โครงสร้างเดิม
จนกว่าจะจบวงจร นี่คือ hysteresis ที่ป้องกัน overfitting-in-motion / chase noise

---

## 4. วงจรชีวิตของโซน (Zone Lifecycle)

ลำดับประมวลผลต่อแท่ง (สำคัญ — เรียงตามความ conservative):

1. **อัปเดตสัญญาณ**: ATR, Anomaly, Regime, EMA trend filter
2. **Take-Profit**: ไม้ที่ `High ≥ TP` ปิดที่ TP (= entry + `tp_mult × spacing`) แล้ว re-arm level เดิม
   (ไม้ที่เพิ่ง fill ในแท่งเดียวกันจะยังไม่ TP ในแท่งนั้น — สมมติฐานแบบ conservative)
3. **Buy fill**: level ที่ `Low ≤ ราคา level` เปิดไม้ตาม size ที่คำนวณไว้ล่วงหน้า
4. **Zone Stop**: ถ้า `Low ≤ stop_price` → ปิดทุกไม้ที่ราคา stop (ขาดทุนรวม ≤ risk_per_zone)
   → เคลียร์โซน → เข้าสู่ **cooldown** (`cooldown_bars` แท่ง)
5. **Anomaly Consolidation**: ถ้าแท่งเคลื่อนลง > `anomaly_z × ATR` → รวบ level ที่ยังไม่ fill
   เป็นคู่ (เหลือครึ่ง) size รวมกัน × `consolidation_scale` เก็บ level ที่ลึกกว่า
   = การกระจุกออเดอร์ **อย่างมีแผน ใต้เพดานความเสี่ยงเดิม** ต่างจาก clustering แบบถัวเฉลี่ยไร้เพดาน
6. **Recenter ขาขึ้น**: ถ้า `Close ≥ center + shift_trigger × spacing` และไม่มีไม้ค้าง
   → สร้างโซนใหม่ที่ราคาปัจจุบัน (spacing ใหม่จาก ATR ปัจจุบัน)

เงื่อนไขการสร้างโซนใหม่ (ทุกกรณี): ATR อุ่นเครื่องแล้ว **และ** พ้น cooldown **และ**
ผ่าน trend filter (`Close ≥ EMA50 − trend_k × ATR`) **และ** regime ≠ `trend_down`

---

## 5. โมเดลความเสี่ยง (Risk per Zone)

Worst case ของโซน = ทุก level fill แล้วราคาหลุด stop:

```
loss_worst = Σᵢ sizeᵢ × (levelᵢ − stop) = equity × risk_per_zone   (โดยนิยาม)
sizeᵢ = (equity × risk_per_zone / N) / (levelᵢ − stop)
```

- แบ่ง risk budget **เท่ากันทุก level** → level ลึกได้ size ใหญ่กว่า (stop ใกล้กว่า)
- ก่อนคูณ regime scale: `risk_per_zone` คือเพดานสัมบูรณ์ต่อวงจรโซน
- ผลลัพธ์: จำนวน stop-out สูงสุดที่พอร์ตรับได้คำนวณล่วงหน้าได้เสมอ
  เช่น risk 2.7%/โซน → โดน stop 10 ครั้งติด เสีย ~24% (ไม่มีทางล้างพอร์ตจากโซนเดียว)

---

## 6. พารามิเตอร์ทั้งหมด (DynamicGridConfig)

### โครงสร้างกริด
| พารามิเตอร์ | default | ช่วง optimize | ความหมาย |
|---|---|---|---|
| `levels` | 6 | 3–10 | จำนวน buy level ต่อโซน |
| `atr_mult` | 1.5 | 0.8–3.0 | order distance (เท่าของ ATR) |
| `atr_period` | 14 | — | คาบ ATR |
| `tp_mult` | 1.0 | 0.8–2.5 | ระยะ TP (เท่าของ spacing) |
| `shift_trigger` | 2.0 | 0.5–3.0 | เกณฑ์ recenter ขาขึ้น |

### ความเสี่ยง
| พารามิเตอร์ | default | ช่วง optimize | ความหมาย |
|---|---|---|---|
| `risk_per_zone` | 0.04 | 0.02–0.08 | เพดานขาดทุนต่อโซน (สัดส่วน equity) |
| `stop_mult` | 1.0 | 0.5–2.0 | ระยะ zone stop ใต้ level ล่างสุด |
| `cooldown_bars` | 20 | 0–80 | แท่งพักหลัง stop-out |
| `trend_k` | 2.0 | 0–6 | ความลึกใต้ EMA ที่ยังยอมสร้างโซน |
| `fee_rate` | 0.0005 | — | ค่าธรรมเนียมต่อ notional ต่อข้าง |

### Anomaly / Consolidation
| พารามิเตอร์ | default | ช่วง optimize | ความหมาย |
|---|---|---|---|
| `anomaly_z` | 3.0 | 2.0–4.5 | เกณฑ์ price anomaly (เท่าของ ATR) |
| `consolidation_scale` | 1.0 | 0.8–1.5 | ตัวคูณ size ตอนรวบโซน |

### Regime Adaptation (v2)
| พารามิเตอร์ | default | ช่วง optimize | ความหมาย |
|---|---|---|---|
| `use_regime` | True | — | เปิด/ปิดโมดูล regime |
| `regime_m_threshold` | 0.5 | 0.2–1.0 | เกณฑ์ momentum แยก trend/sideways |
| `regime_vol_hi` | 1.4 | 1.1–1.8 | เกณฑ์ vol ratio เข้า high_vol |
| `hv_risk_scale` | 0.5 | 0.3–1.0 | ลด risk เมื่อ high_vol |
| `hv_spacing_scale` | 1.4 | 1.0–2.0 | ถ่างกริดเมื่อ high_vol |
| `up_risk_scale` | 1.2 | 0.8–1.6 | เพิ่ม risk เมื่อ trend_up |

---

## 7. Multi-Layer Grid Orchestrator (v3)

### 7.1 แนวคิด

โซนเดียวจับได้แค่ 1 สเกลความผันผวนต่อรอบ (spacing คงที่ตลอดอายุโซน) แต่ตลาดจริง
มีทั้งการแกว่งไว (noise รายวัน) และการแกว่งช้า (swing ใหญ่) ซ้อนกันอยู่ตลอดเวลา
Multi-Layer แก้ปัญหานี้ด้วยการรัน `DynamicGridEngine` **หลายชุดพร้อมกัน** คนละสเกล
ราคา แล้วให้ `MultiLayerOrchestrator` เป็นผู้แบ่ง equity/risk budget ระหว่างชั้น:

```
MultiLayerOrchestrator
 ├─ layer "fast"  (atr_mult เล็ก)  น้ำหนัก 10%  → เก็บกำไรจาก noise ถี่ๆ
 ├─ layer "core"  (atr_mult ฐาน)   น้ำหนัก 70%  → โครงหลัก (ค่าที่จูน+validate แล้วจาก v2)
 └─ layer "wide"  (atr_mult ใหญ่)  น้ำหนัก 20%  → รอจับ swing ใหญ่ ไม่ตื่นตามสัญญาณรบกวน
```

แต่ละ layer มี **zone stop / cooldown / regime gate ของตัวเองครบ** (เป็น
`DynamicGridEngine` อิสระ) — ความเสี่ยงจึงไม่ทบซ้อนแบบไม่มีเพดาน แต่ถูก
partition ด้วย weight ตั้งแต่ต้น:

```
total_worst_case_loss ≤ equity × Σ(weightᵢ × risk_per_zoneᵢ)
```

### 7.2 การ derive พารามิเตอร์ต่อ layer (`make_layers`)

การ rescale เฉพาะ spacing (`atr_mult`) โดยไม่แตะ `stop_mult` ทำให้ **layer fast
ตายเร็วเกินไป** — พิสูจน์ด้วยการทดสอบจริง: fast layer เดี่ยวๆ (atr_mult เล็กแต่
stop_mult เท่าเดิม) โดน stop-out ถึง 60 ครั้งในฉาก **sideways ธรรมดา** (ซึ่ง
core layer โดน 0 ครั้ง) เพราะ stop อยู่ใกล้เกินไปในหน่วย ATR จริง จึงต้อง
rescale `stop_mult` ตามสัดส่วนผกผันด้วย:

```python
fast.atr_mult  = base.atr_mult * fast_scale       # spacing แคบลง
fast.stop_mult = base.stop_mult / fast_scale      # stop กว้างขึ้นชดเชย (คงที่ในหน่วย ATR)
fast.risk_per_zone = base.risk_per_zone * 0.5     # โดน stop บ่อยกว่า -> เจ็บต่อครั้งน้อยลง
```

ค่า default: `fast_scale=0.7, wide_scale=2.0`, น้ำหนัก `fast=10%, core=70%, wide=20%`
(ได้จากการ sweep น้ำหนักหลายชุดบน 6 scenario × 3 seed แล้วเลือกจุดที่ให้ผลตอบแทน
ดีที่สุดในกลุ่มที่ยังลด DD ได้จริงทุก scenario)

### 7.3 ผลทดสอบ: Single-layer vs Multi-layer

พารามิเตอร์ core = config แนะนำจาก v2 (held-out validated), 3 seeds/scenario:

| Scenario | Single ret/wDD | Multi ret/wDD |
|---|---|---|
| sideways | +2.84% / 2.24% | +2.20% / **1.79%** |
| uptrend | +2.18% / 1.11% | +1.90% / **0.95%** |
| downtrend | −4.61% / 6.66% | −4.01% / **5.68%** |
| crash | +1.25% / 4.26% | +0.52% / **3.81%** |
| regime_switch | +0.36% / 3.04% | +0.17% / **2.92%** |
| high_vol | +1.01% / 1.69% | +0.70% / **1.39%** |
| **mean return** | **+0.50%** | +0.25% |

**สรุปแบบตรงไปตรงมา**: Multi-Layer ลด max drawdown ได้ **ทุก scenario** (12–20%
เมื่อเทียบสัมพัทธ์) แลกกับ return เฉลี่ยที่ลดลงราวครึ่งหนึ่ง — เป็น trade-off
ที่ตรงตามปรัชญาของระบบ (ข้อ 1: Robustness ก่อน Return) ไม่ใช่ "ดีกว่าทุกด้าน"
เหมาะกับผู้ใช้ที่ต้องการ equity curve เรียบขึ้นและยอมรับ upside ที่ลดลง
ไม่เหมาะถ้าเป้าหมายคือ maximize return บนพารามิเตอร์ core ที่ validate แล้ว

### 7.4 วิธีใช้งาน

```python
from dynamic_grid import DynamicGridConfig, MultiLayerOrchestrator, make_layers, run_backtest_engine

base_cfg = DynamicGridConfig(levels=10, atr_mult=2.642, risk_per_zone=0.027, ...)
layers = make_layers(base_cfg)              # สร้าง 3 layer (fast/core/wide)
orch = MultiLayerOrchestrator(layers)
result = run_backtest_engine(ohlc, orch)     # backtester เดิม ใช้กับ orchestrator ได้ทันที
for ls in orch.layer_stats():                # ดู breakdown รายชั้น
    print(ls.name, ls.weight, ls.n_tp, ls.n_stopouts)
```

`run_backtest_engine` (ใน backtest.py) รับ **engine ตัวใดก็ได้ที่มี interface
`on_bar/unrealized/n_tp/n_stopouts/n_rebuilds/n_consolidations`** — ใช้ได้ทั้ง
`DynamicGridEngine` เดี่ยวและ `MultiLayerOrchestrator` โดยไม่ต้องแก้ backtester

### 7.5 ข้อจำกัดของ v3 (เพิ่มเติมจากข้อ 10)

- ยังไม่มี **cap เพดาน exposure รวม** ข้าม layer (แต่ละ layer อิสระต่อกันเต็มที่ —
  ในทางทฤษฎีถ้าทุก layer เปิดโซนพร้อมกันในจังหวะเดียว exposure จะสูงกว่า
  single-layer ชั่วขณะหนึ่ง แม้ risk budget ต่อโซนจะถูก partition แล้วก็ตาม)
- น้ำหนัก/สเกลของแต่ละ layer ยังเป็นค่าคงที่ (ไม่ได้ optimize เต็มรูปแบบแบบ
  random search เหมือนพารามิเตอร์ core — ใช้วิธี sweep กริดหยาบเท่านั้น)
- ยังไม่ทดสอบ 4+ layer หรือ layer ที่ต่างกันด้าน regime response (เช่น layer
  เฉพาะสำหรับ high_vol เท่านั้น)

---

## 7B. State-based Momentum Confirmation (v3.1)

### แนวคิด

เดิมระบบกรอง momentum เฉพาะตอน**สร้างโซน** (regime gate) แต่ level ในโซนที่เปิด
อยู่แล้วยัง fill สวน sell-off ได้ — ราคาแตะ level = ซื้อทันที ไม่สนว่าแท่งนั้น
กำลังเทขายรุนแรงอยู่ v3.1 เพิ่มการยืนยันที่ชั้น **fill รายแท่ง**: ระดับราคา
อย่างเดียวไม่ใช่เหตุผลให้ซื้อ ต้องไม่อยู่ในสถานะเทขายด้วย

```
selling_off = (แท่งนี้เป็น down-anomaly) OR (momentum < -entry_m_block)
if selling_off: level ค้างสถานะ pending ไว้ -> ไป fill แท่งถัดไปที่ตลาดนิ่งกว่าแทน
```

สำคัญ: ไม่ใช่การยกเลิกออเดอร์ — level ยัง pending อยู่ แค่**เลื่อนจังหวะ**เข้า
ให้พ้นแท่งที่มีดตก (บ่อยครั้งได้ราคาเท่าเดิมหรือดีกว่าในแท่งถัดไป)

### ผล Ablation (held-out seeds 7/11/13, base = config แนะนำ v2)

| ตัวชี้วัด (เฉลี่ย 6 ตลาด) | OFF (baseline) | ON blk=0.5 | ON blk=1.5 |
|---|---|---|---|
| Mean return | **+0.50%** | −0.11% | +0.22% |
| Mean CVaR 5% | −0.121% | **−0.083%** | −0.100% |
| Worst DD (downtrend) | 6.66% | **5.69%** | 6.36% |
| Robust score (เกณฑ์กลางของระบบ) | −0.0734 | **−0.0620** | −0.0686 |

**คำตัดสิน**: เมื่อวัดด้วย robust score ที่ระบบใช้เป็นเกณฑ์มาตลอด (ลงโทษ DD หนัก
กว่า return 2 เท่า — ประกาศไว้ก่อนการทดลอง ไม่ใช่เลือกเกณฑ์หลังเห็นผล)
momentum confirmation **ชนะทุกค่า threshold** และดีสุดที่ `entry_m_block=0.5`
ข้อแลกเปลี่ยนคือ return เฉลี่ยลดลง แต่ tail risk (CVaR) ดีขึ้น ~31% และ DD
ขาลงลดลง — ตรงปรัชญาข้อ 1 จึง**รับเข้าเป็นส่วนหนึ่งของ config แนะนำ**

หมายเหตุความซื่อสัตย์กับข้อมูล: ถ้าตัดสินด้วย return อย่างเดียว ฟีเจอร์นี้จะ "แพ้"
— การเลือกเกณฑ์ตัดสิน**ก่อน**ทำการทดลองคือสิ่งที่ทำให้ workflow นี้เชื่อถือได้

### พารามิเตอร์ใหม่

| พารามิเตอร์ | default (dataclass) | ค่าแนะนำ | ความหมาย |
|---|---|---|---|
| `momentum_confirm` | False* | **True** | เปิดการยืนยัน momentum ที่ชั้น fill |
| `entry_m_block` | 1.0 | **0.5** | ระงับ fill เมื่อ momentum < −ค่านี้ |

*default ใน dataclass คงเป็น False เพื่อให้ผลทดสอบ v1/v2 เดิม reproduce ได้ —
config แนะนำ (หัวข้อ 10) เป็นผู้ถือค่าที่พิสูจน์แล้ว

## 7C. ตัวชี้วัดเชิงลึก (Deep Evaluation Metrics, v3.1)

`BacktestResult` เพิ่ม 3 ตัวชี้วัดตามหลักการ "ไม่ดูแค่ Net Profit / %Win":

| ตัวชี้วัด | นิยามในระบบ | ตอบคำถาม |
|---|---|---|
| `cvar_5` | ค่าเฉลี่ยผลตอบแทนรายแท่งของ 5% ที่แย่ที่สุด (Expected Shortfall) | วันที่เลวร้ายจริงๆ เสียหายเท่าไหร่ (ลึกกว่า maxDD ที่เป็นจุดเดียว) |
| `profit_factor` | กำไรรวมจากไม้ TP ÷ ขาดทุนรวมจากไม้ stop-out (ระดับรายไม้ ไม่ใช่จาก equity curve) | เครื่องจักรทำกำไรมีประสิทธิภาพแค่ไหนต่อการเสีย 1 หน่วย |
| `recovery_factor` | กำไรสุทธิ ÷ มูลค่า drawdown สูงสุด | ระบบฟื้นจากหลุมได้คุ้มความเจ็บไหม |

ข้อสังเกตจากการใช้จริง: Profit Factor ของกริดใน sideways จะสูงผิดปกติ (ไม่มี
stop-out เลย → PF เข้าใกล้อนันต์, ใน report จะ cap ที่ 99) — ตัวที่แยกแยะระบบได้
จริงคือ PF ใน downtrend/crash ซึ่งบอกว่าเครื่องจักรเสียหายหนักแค่ไหนเมื่อตลาดร้าย

## 7D. Structured Decision Logging (v3.3) — รากฐาน MAS / Cognee / Virtual Office

ต่อยอดแนวคิด multi-agent + AI memory (Cognee) + Virtual Office: ระบบเรามี "แหล่ง context"
อยู่แล้ว (trade log, regime, risk) แต่ยังคืนเป็น object/CSV — v3.3 เพิ่มชั้น logging ที่แปลง
การตัดสินใจของแต่ละ agent เป็น **structured event + natural-language knowledge statement**

`dynamic_grid/event_log.py`:
- `DecisionEvent` — 1 การตัดสินใจ: `bar, agent_id, decision, reason, price, regime,
  momentum, equity, extra` (decision ∈ build_zone / skip_build / fill / entry_block /
  take_profit / stop_out / consolidate / recenter)
- `DecisionLog` — เก็บ event จากหลาย agent, export ได้ 2 แบบ:
  - `.to_jsonl()` → JSON Lines สำหรับ ingest เข้า Cognee / memory store
  - `.to_knowledge_file()` → ประโยคภาษาธรรมชาติ 1 บรรทัด/event สำหรับ knowledge graph
    (เช่น *"At bar 863, agent 'fast' cut the whole zone at its stop because price hit
    zone stop... Regime was trend_down (momentum -2.12)..."*)
  - `.summary()` → digest แบบที่ orchestrator agent อ่านกลับได้ (นับตาม agent/decision)

**Opt-in และไม่กระทบผลเดิม**: `DynamicGridEngine(cfg, logger=None)` (default) ทำงาน
เหมือนเดิมทุกไบต์ — ผลทดสอบ v1-v3.2 ทั้งหมด reproduce ได้ (ยืนยันด้วย regression) การ log
เกิดเฉพาะเมื่อแนบ `DecisionLog` เข้าไป และตั้ง `agent_id` ให้แต่ละ layer

`logging_demo.py`: รัน 3 layer (fast/core/wide) เป็น **named agents เขียนลง log ก้อนเดียว**
= รูปแบบ MAS ที่แชร์ memory ขั้นต่ำสุด → บันทึก `results/decision_events.jsonl` +
`results/decision_knowledge.txt`

**หลักการเก็บ knowledge ที่ย้ำไว้ในโค้ด**: negative results (config ไหน overfit, walk-forward
finding, seed sensitivity) มีค่ากว่า trade log ที่กำไร — ควร persist ลง graph ก่อน ไม่ใช่เก็บ
แต่ผลสวยจนหลอกตัวเอง (บทเรียนตรงจากหัวข้อ 13)

### ต่อ Cognee จริง (v3.3)

`dynamic_grid/cognee_adapter.py` — bridge จาก `DecisionLog` เข้า **Cognee**
(github.com/topoteretes/cognee, self-hosted knowledge-graph memory):
- `push_log(log)` — ingest knowledge statements ของทุก decision
- `push_findings(PROJECT_FINDINGS)` — ingest บทเรียน/negative results (walk-forward
  Static>Dynamic, overfitting, seed sensitivity) — ชุด finding เขียนไว้ในไฟล์แล้ว
- `recall(query)` — ให้ orchestrator agent ถามกลับก่อนตัดสินใจ

ออกแบบให้ทนทาน: (1) **cognee เป็น optional dependency** ไม่ได้ติดตั้งใน dev env นี้ —
import ถูก guard, ถ้าไม่มีจะขึ้น error พร้อมวิธีติดตั้ง (`uv pip install cognee` + ตั้ง
`LLM_API_KEY`) ไม่ใช่ crash; (2) **รองรับหลายเวอร์ชัน API** — feature-detect ตอนรันว่า cognee
ที่ติดตั้งมี `remember`/`recall` (API ใหม่) หรือ `add`+`cognify`+`search` (API classic)
แล้วใช้อันที่มี; (3) เป็น async ทั้งหมด มี sync wrapper ให้

`cognee_demo.py` — รัน grid → log → push เข้า Cognee → recall (ถ้ายังไม่ติดตั้ง cognee
จะพิมพ์ payload ที่จะ push ให้ตรวจก่อน)

### Virtual Office front-end (v3.4)

`virtual_office.html` — web app ไฟล์เดียว (HTML5 + vanilla JS + canvas, ไม่มี dependency)
ตามแนวเดียวกับ Virtual Office ของผู้ใช้: อ่าน `results/decision_events.jsonl` มา animate
การทำงานของทีม agent ต่อ bar

- **Office floor**: agent แต่ละตัว (fast/core/wide — detect อัตโนมัติจาก log รองรับกี่ตัวก็ได้)
  มีโต๊ะ+จอแสดง equity, status pill (TRADING เขียว / COOLDOWN แดง / WAIT-regime เหลือง /
  IDLE เทา) พร้อม glow + speech bubble ตอนตัดสินใจ
- **Shared Memory hub** ตรงกลางเชื่อมทุก agent (สื่อภาพว่า log/knowledge เป็นของกลาง)
- **Price wall** ด้านบน (ใช้เฉพาะ market-price events — build/skip/recenter ไม่ปนราคา TP/stop)
- **Decision feed** ขวามือ = มุมมอง shared memory แบบ scroll, **playback**: play/pause,
  speed x1–x40, scrub ไป bar ไหนก็ได้ (สถานะ rebuild แบบ deterministic จาก log)
- โหลดข้อมูล 3 ทาง: fetch อัตโนมัติเมื่อ serve ผ่าน `python -m http.server`, ลากไฟล์วาง,
  หรือปุ่มเลือกไฟล์

ทดสอบจริงผ่าน browser preview แล้ว: state ต่อ bar ตรงกับ log (เช่น core โดน stop_out ที่
bar 898 → pill เปลี่ยนเป็น COOLDOWN, fast โดน trend filter → WAIT) — บั๊กที่เจอและแก้ระหว่าง
ทดสอบ: canvas height feedback loop (แก้ด้วย absolute positioning) และกราฟราคาปนราคา
level/TP (แก้ด้วยการกรอง event type)

### Memory-loop Orchestrator (v3.5) — ปิด loop: อ่าน memory กลับมาปรับการตัดสินใจ

`dynamic_grid/orchestrator_agent.py` — `MemoryOrchestrator` ขับ layer engines เหมือน
MultiLayerOrchestrator แต่ทุก 200 แท่งจะ **อ่าน shared DecisionLog** แล้วใช้กฎ governance
ที่ประกาศไว้ล่วงหน้า:

- **RULE 1 (cut)**: layer ที่โดน stop-out ในรอบ review → หั่น risk budget ครึ่งหนึ่ง (floor 0.25)
  = หลัง stop กลับเข้าที่ half-size (anti-martingale / equity-curve throttling)
- **RULE 2 (restore)**: layer ที่รันสะอาด (มี TP, ไม่มี stop) → คืน budget เท่าตัว (cap 1.0)
  — การฟื้นต้อง earn ด้วยหลักฐาน ไม่ใช่แค่เวลาผ่านไป

ทุก intervention ถูก log กลับเข้า DecisionLog เดียวกัน (agent_id="orchestrator") →
Virtual Office แสดงเป็นโต๊ะที่ 4, Cognee ได้ reasoning ครบ, audit trail สมบูรณ์

**ผล A/B (เกณฑ์ประกาศก่อนรัน: robust score = return − 2×maxDD, 6 scenario × 3 seeds):**

| | OFF (fixed weights) | ON (memory loop) |
|---|---|---|
| Mean robust score | −0.0383 | **−0.0342** |
| downtrend | −4.01% / DD 5.68% | **−3.36% / DD 5.36%** |
| regime_switch DD | 2.92% | **2.53%** |
| sideways/uptrend/high_vol | — | เท่าเดิม/ต่างระดับ rounding |

**คำตัดสิน**: ON ชนะตามเกณฑ์ (~11% ดีขึ้น) โดยดีขึ้นตรงจุดที่ควรดี (ตลาดร้าย) และแทบไม่เสีย
อะไรในตลาดดี — ปรับปรุงเล็กน้อยแต่มาจากกลไกที่อธิบายได้และตรวจสอบย้อนหลังได้ทุกการตัดสินใจ

**บันทึกความซื่อสัตย์ (สำคัญ)**: กฎเวอร์ชันแรก (threshold=2 ใน 50 แท่ง) **ตายเชิงกลไก** —
cooldown ของ layer อยู่ที่ 36–109 แท่ง จึงเป็นไปไม่ได้ที่จะ stop 2 ครั้งใน 50 แท่ง ผล A/B
รอบแรกออกมาเท่ากันเป๊ะเพราะ orchestrator ไม่เคยทำอะไรเลย การปรับเป็น threshold=1/200 แท่ง
ทำ**ก่อน**ดูคะแนน ON-vs-OFF (ปรับเพราะกฎไม่ feasible ไม่ใช่เพราะแพ้) — และ intervention
log ใน demo พิสูจน์ว่า loop ทำงานจริง (cut ตอนโดน stop, restore ตอนรันสะอาด)

รัน: `python orchestrator_demo.py` | `logging_demo.py` เปลี่ยนมาใช้ MemoryOrchestrator แล้ว
ดังนั้น log ที่ Virtual Office อ่านจะมี governance events (⚖️ risk_cut / 🔓 risk_restore) ด้วย

**สิ่งที่ยังต้องทำเพื่อครบ stack**: (1) รัน `cognee_demo.py` ในเครื่องที่ติดตั้ง cognee +
LLM key จริง เพื่อยืนยัน API ตรงกับเวอร์ชันที่ผู้ใช้ใช้ (dev env นี้ยืนยันไม่ได้)
(2) ให้ orchestrator query Cognee (`recall()`) ประกอบการตัดสินใจ — ตอนนี้อ่านจาก DecisionLog
ในเครื่อง ยังไม่ผ่าน knowledge graph
(3) ต่อ Virtual Office เข้ากับ live run / Cognee query แทนไฟล์ log สถิต

---

## 8. สภาพแวดล้อมทดสอบ (Synthetic Scenarios)

ทุก scenario: 2,000 แท่ง OHLC, intrabar จำลองด้วย 8 sub-steps, ราคาเริ่ม 100
(mu/sigma = ค่ารวมทั้งซีรีส์)

| Scenario | แบบจำลอง | จำลองสภาวะ |
|---|---|---|
| `sideways` | OU process (θ=8, σ=0.6) | แกว่งกรอบ ±15% — บ้านของระบบกริด |
| `uptrend` | GBM (μ=+0.9, σ=0.35) | ขาขึ้นแรง — ทดสอบ opportunity cost / recenter |
| `downtrend` | GBM (μ=−0.9, σ=0.35) | ขาลงแรง — ตัวฆ่ากริดคลาสสิก |
| `crash` | GBM + jump ลง 6–15% × 3 ครั้ง | Price anomaly — ทดสอบ consolidation |
| `regime_switch` | 5 บล็อกสลับโหมด | ทดสอบการปรับตัวข้าม regime |
| `high_vol` | GBM (σ=1.0) | ผันผวนจัด — ทดสอบ vol scaling |

---

## 9. วิธี Optimization

- **Random search** บน search space 15 พารามิเตอร์ (150+ iterations)
- ทดสอบทุกชุดกับ **ทุก scenario × หลาย seed พร้อมกัน** (12 backtests/ชุด)
- คะแนน robust: `mean(return − 2×maxDD) − 0.5×std` —
  DD ถูกลงโทษหนักกว่า return 2 เท่า และลงโทษความไม่สม่ำเสมอข้ามตลาด
- เจตนา: หาชุดเดียวที่ **รอดทุกตลาด** ไม่ใช่ชุดที่ชนะตลาดเดียว (กัน overfit)

## 10. ผลทดสอบล่าสุด (single-layer core config)

### Static vs Dynamic (พารามิเตอร์จูนแล้ว, seed 7)

| Scenario | Static return/DD | Dynamic return/DD |
|---|---|---|
| sideways | +1.7% / 0.7% | +2.5% / 0.9% |
| uptrend | +1.1% / 0.8% | +2.6% / 0.9% |
| downtrend | −22.4% / 22.8% | **−4.9% / 5.2%** |
| crash | −6.8% / 14.0% | **+1.7% / 3.5%** |
| regime_switch | +1.9% / 1.0% | +0.2% / 2.4% |
| high_vol | −1.7% / 3.7% | +1.1% / 1.1% |

(Static แบบ default ที่ไม่จูน: downtrend −76% / DD 77% — จุดอ้างอิงปัญหา "โดนลาก")

### Ablation v1 vs v2 (regime module, 3 seeds, พารามิเตอร์ฐานเดียวกัน)

| | v1 (ไม่มี regime) | v2 (มี regime) |
|---|---|---|
| return เฉลี่ย 6 ตลาด | +0.28% | **+0.50%** |
| worst DD (ทุกตลาด) | ≤ 6.6% | ≤ 6.7% |

regime module เพิ่ม return เฉลี่ย ~79% โดย DD แทบไม่เปลี่ยน (ใช้ regime params แบบ default)

### บทเรียนจากการจูน regime แรงเกินไป (บันทึกไว้เป็นหลักฐาน)

ทดลอง fine-tune เฉพาะ regime params 5 ตัว (40 iterations บน seeds 1–2) ได้คะแนน
in-sample ดีที่สุด (−0.0953) แต่เมื่อ validate บน **held-out seeds (7, 11, 13)**
return เฉลี่ยตกเหลือ +0.12% — แพ้ regime แบบ default (+0.50%) ชัดเจน

**ข้อสรุปเชิงนโยบาย**: พารามิเตอร์ชั้น regime มีความไวต่อ noise สูง ให้ใช้ค่า default
ที่ตั้งจากเหตุผล (ผันผวนสูง→ไม้เล็กกริดถ่าง) แทนค่าที่จูนจนสุด และการจูนทุกครั้ง
**ต้องมี held-out validation** — คะแนน in-sample อย่างเดียวเชื่อไม่ได้

### Config แนะนำปัจจุบัน (best known, ผ่าน held-out validation)

```python
DynamicGridConfig(
    levels=10, atr_mult=2.642, risk_per_zone=0.027, stop_mult=0.59,
    shift_trigger=2.587, anomaly_z=2.389, consolidation_scale=1.174,
    cooldown_bars=73, tp_mult=1.765, trend_k=2.383,
    use_regime=True,            # regime params ใช้ default ทั้งหมด
    momentum_confirm=True,      # v3.1: ยืนยัน momentum ที่ชั้น fill
    entry_m_block=0.5,          # (ผ่าน ablation + robust score บน held-out seeds)
)
```

---

## 11. ข้อจำกัดที่ทราบ (Known Limitations)

1. ทดสอบกับ synthetic data เท่านั้น — ยังไม่ผ่าน walk-forward กับข้อมูลจริง
2. ไม่มี slippage จำลอง, funding rate, partial fill (มีเฉพาะ fee 0.05%/ข้าง)
3. Long-accumulation เท่านั้น — ขาลงทำได้แค่ "หลบให้รอด" ยังไม่ทำกำไร
4. สมมติฐาน fill แบบ bar-sweep (Low แตะ = fill) — มองโลกแง่ดีกว่า order book จริงเล็กน้อย
5. Random search 150 iters บน 15 มิติยังหยาบ — ควรอัปเกรดเป็น Bayesian/CMA-ES
6. ตัวเลข return บน synthetic ใช้เปรียบเทียบ **เชิงสัมพัทธ์** (Static vs Dynamic, v1 vs v2)
   ไม่ใช่การพยากรณ์ผลตอบแทนจริง

## 12. Roadmap

- [x] ~~**Multi-Layer Grid**: หลาย engine คนละสเกล ATR + orchestrator แบ่ง risk budget รวม~~ (v3)
- [x] ~~**เพดาน exposure รวมข้าม layer**~~ (v3.2) — ดูหัวข้อ 7.5b
- [x] ~~**Walk-forward กับข้อมูลจริง**~~ (v3.2) — ดูหัวข้อ 13 (ข้อมูล BTC/USDT จริง) — **critical finding ไม่ใช่ pass/fail**
- [x] ~~**แก้ overfitting-to-regime ที่ walk-forward เจอ**~~ (v3.2.1, sub-window robust scoring) —
  **แก้ได้บางส่วนเท่านั้น**: ลด tail risk ได้จริงมาก แต่ Static ยังชนะ mean/median return บน BTC/USDT จริง
- [ ] **Optimize น้ำหนัก/สเกลของ layer** ด้วย random search เต็มรูปแบบ (ตอนนี้ sweep หยาบ)
- [ ] **เพิ่ม n_iter ของ walk-forward optimizer** — ผลยังไวต่อ seed มาก (60 iterations น้อยไป)
- [ ] **Learning loop / RL**: policy ปรับพารามิเตอร์ตาม regime แทน scale คงที่
- [ ] **Short-side grid**: ทำกำไรใน trend_down แทนการหลบอย่างเดียว
- [ ] Regime classifier ขั้นสูง (ML) แทน rule-based — เฉพาะเมื่อ rule-based ถึงเพดาน
- [ ] ข้อมูลจริงเพิ่มเติม: multi-asset, ช่วงเวลายาวขึ้น/ตลาดหมีจริง (1000 bars ปัจจุบันไม่มีตลาดหมีเต็มรูปแบบ)

### 7.5b เพดาน Exposure รวมข้าม Layer (v3.2)

`MultiLayerOrchestrator(layers, max_gross_exposure=0.5)` — ก่อนประมวลผลแต่ละแท่ง
ถ้า exposure รวมทุก layer ≥ เพดานที่ตั้ง จะเลื่อนการสร้างโซนใหม่ (ไม่ใช่ปิดโซนที่เปิดอยู่)
ของทุก layer ที่ว่างอยู่ (`center is None, cooldown == 0`) ออกไป 1 แท่ง กันไม่ให้ layer ใหม่ๆ
มาซ้อนความเสี่ยงตอน exposure สูงอยู่แล้ว

**ผลทดสอบตรงไปตรงมา**: กลไกทำงานถูกต้อง (ยืนยันด้วยการทดสอบตรง — fire ได้จริงเมื่อเงื่อนไขตรง)
แต่ในโครงสร้าง layer ปัจจุบัน (fast/core/wide ใช้ regime gate ร่วมกัน) แทบไม่ fire เลย
เพราะ layer ทั้ง 3 มักเปิด/ปิดโซนพร้อมกัน (correlated) ไม่ใช่กระจายอิสระ — เพดานนี้จึงเป็น
**safety net สำหรับอนาคต** (เมื่อ layer มี regime gate อิสระต่อกันมากขึ้น) มากกว่าที่จะเปลี่ยนผล
บน default config วันนี้ — บันทึกไว้ตามจริง ไม่ได้อ้างว่าเพดานนี้ "แก้ปัญหา" อะไรในทางปฏิบัติตอนนี้

## 13. Walk-Forward on Real Data (v3.2) — the most important section in this doc

หลังจากทุก version ก่อนหน้าทดสอบกับ synthetic data เท่านั้น (และเตือนไว้ทุกครั้งว่านี่คือข้อจำกัด)
v3.2 รันผ่านข้อมูลจริงครั้งแรก: **BTC/USDT รายวัน 1000 แท่ง (ต.ค. 2023 – ก.ค. 2026)**
จาก Binance public API (`data/btc_binance_1d.json`) — ครอบคลุมตลาดกระทิงยาว + จุดพีค + การปรับฐาน 2026

**Protocol**: walk-forward แบบมาตรฐาน — train 250 วัน (optimize พารามิเตอร์) → test 60 วันถัดไป
(ไม่เห็นตอน optimize) → เลื่อนหน้าต่าง 60 วัน → ทำซ้ำ (`dynamic_grid/walk_forward.py`,
รันด้วย `python walk_forward_demo.py`)

### ผลลัพธ์รอบแรก (single seed, 12 folds) — สาเหตุที่พบ overfitting-to-regime

รอบแรกใช้ optimizer ที่จูนกับ**ทั้ง train window เป็นก้อนเดียว** (250 วัน) พบว่า Static
ชนะ Dynamic ทุกตัวชี้วัด (mean return +2.76% vs +0.76%, worst maxDD 5.27% vs 8.11%)
วิเคราะห์ fold 0 พบสาเหตุชัดเจน: train window เป็นขาขึ้นแรง +142.6% (26,862 → 65,175)
optimizer จึงเลือกพารามิเตอร์ที่เหมาะกับการรันยาวไม่หยุด จากนั้น test window เจอการปรับฐาน
เพียง -8.4% ซึ่งมากพอให้ **zone stop ของ Dynamic** ทำงานแล้วเข้า cooldown — พอราคาเด้งกลับ
ใน 60 วันเดียวกัน Dynamic ไม่ได้อยู่ในตลาดแล้ว ขณะที่ Static ถือยาวเก็บกำไรได้เต็มๆ
(+26.88% vs Dynamic +3.27% ใน fold นี้) — **นี่คือ overfitting-to-regime**: optimizer
จูนบน 1 training window เดียวต่อ fold ต่างจาก synthetic optimizer ที่จูนข้าม 6 scenario
พร้อมกันเพื่อกัน overfit โดยเฉพาะ

### แก้ไข (v3.2): sub-window robust scoring ในตัว optimizer ของ walk-forward

`_optimize_on_window()` เปลี่ยนจากให้คะแนนด้วย train window ก้อนเดียว เป็นแบ่ง train
เป็น 4 sub-window ที่ทับซ้อนกันกระจายทั่ว train (early/mid/late) แล้วให้คะแนนแบบ
`mean(sub-window scores) − 0.5×std(sub-window scores)` — สูตรเดียวกับ robust score
ของ synthetic optimizer ทุกประการ เพียงใช้ sub-window ของอนุกรมจริงแทน scenario สังเคราะห์
พารามิเตอร์ที่เหมาะกับแค่ regime เดียวใน train จะได้คะแนนแย่ลงเพราะ sub-window อื่นให้ผลต่างกัน

### ผลลัพธ์หลังแก้ (สำคัญ: aggregate ข้าม 5 seeds × 12 folds = 60 fold-runs ไม่ใช่ seed เดียว)

การทดสอบรอบแรกที่รายงานว่า "Dynamic ชนะ" นั้นเป็น **seed เดียว (seed=0) ที่บังเอิญได้ผลดี** —
พอรัน 5 seeds แล้วรวมผล (แทนที่จะเลือกโชว์ seed ที่ดูดี) ภาพที่ซื่อสัตย์กว่าคือ:

| | OLD (train ก้อนเดียว) | NEW (sub-window robust) |
|---|---|---|
| Dynamic mean return | +0.81% | +0.57% |
| Dynamic median return | +1.15% | +0.47% |
| Dynamic worst maxDD | 8.11% | **5.68% (5 seeds), 7.08% (สูงสุดที่เจอ)** |
| Static mean return | +1.83% | +1.32% |
| Static median return | +0.53% | **+0.03%** |
| Static worst maxDD | **21.47%** | **3.56%** |

**คำตัดสินที่ซื่อสัตย์**: การแก้ไขนี้ **ลด tail risk ได้จริงและมาก** (worst maxDD ของ Static
เอง ลดจาก 21.47% → 3.56% เพราะพารามิเตอร์ที่เลือกไม่ผูกกับ regime สุดโต่งของ train
window เดียวอีกต่อไป) แต่**ไม่ได้พลิกข้อสรุปหลัก** — Static ยังชนะ Dynamic ทั้ง mean และ
median return ใน BTC/USDT ข้อมูลจริงชุดนี้ ทั้ง OLD และ NEW method

การรายงานแบบ single-seed (เหมือนที่ทำไปรอบแรก) เป็นความเสี่ยงเดียวกับ overfitting ที่กำลัง
พยายามแก้ — **บทเรียนนี้สำคัญพอๆ กับผลลัพธ์เอง**: ต้อง aggregate หลาย seed ก่อนสรุปเสมอ
ไม่ใช้แค่ค่าที่ optimizer สุ่มมาได้ดีในรอบเดียว

### ข้อจำกัดของการทดสอบนี้ (ต้องอ่านก่อนเชื่อผลข้างต้น)

1. สินทรัพย์เดียว (BTC/USDT), exchange เดียว (Binance) — ยังไม่ผ่าน cross-asset validation
2. Optimizer 60 iterations/fold (น้อยกว่า synthetic ที่ใช้ 150) — in-sample fit หยาบ
   และผลลัพธ์ยังไวต่อ seed มาก (ดูตารางข้างบน) — ต้องการ n_iter ที่สูงกว่านี้เพื่อลด noise
3. มีแค่ 12 OOS folds ต่อ seed — น้อยเกินกว่าจะเชื่อสถิติแบบ Sharpe ได้ อ่านเป็น "ทิศทาง" ไม่ใช่ข้อสรุปสุดท้าย
4. ไม่มี slippage model นอกจาก fee_rate เดิม — การ fill จริงจะแย่กว่านี้
5. 1000 แท่งครอบคลุมแค่ตลาดกระทิงยาว + การปรับฐาน — **ไม่มีตลาดหมีจริงหรือ sideways หลายปี**
   ในข้อมูลชุดนี้เลย ซึ่งเป็นจุดที่ Dynamic ควรจะเด่นตาม synthetic downtrend/crash tests —
   เป็นไปได้ว่า Dynamic จะกลับมาเด่นกว่าถ้าทดสอบในช่วงตลาดหมีจริง แต่**ยังพิสูจน์ไม่ได้ด้วยข้อมูลที่มี**

### สิ่งที่ต้องทำต่อ (ยังไม่ "เสร็จ" — แก้ได้แค่บางส่วน)

- เพิ่ม `n_iter` ต่อ fold (ตอนนี้ 60) เพื่อลด seed-sensitivity ที่เห็นชัดในตาราง
- หาข้อมูลจริงที่มีตลาดหมีเต็มรูปแบบมาทดสอบ (1000 แท่งฟรีจาก Binance ไม่ครอบคลุม)
- ทดสอบ cross-asset (ETH, altcoin ผันผวนสูง) ก่อนสรุปว่า Dynamic ใช้ได้จริง
- พิจารณาว่า Static ที่ชนะอยู่นี้ยังไม่เคยเจอ synthetic downtrend/crash ในข้อมูลจริง —
  ผลลัพธ์นี้อาจเปลี่ยนทันทีที่มีข้อมูลตลาดหมีจริงมาทดสอบ

**ข้อสรุปเชิงนโยบาย**: อย่าเชื่อผล synthetic backtest ของระบบนี้ (v1-v3.1) ว่าเป็นข้อพิสูจน์ความเหนือกว่า
ของ Dynamic Grid ในตลาดจริง — synthetic data ใช้พิสูจน์ "กลไกทำงานตามที่ออกแบบ" เท่านั้น
sub-window fix ช่วยลด tail risk ได้จริงแต่ยังไม่พลิกผล **ยังไม่ควรใช้ระบบนี้เทรดเงินจริง**
จนกว่าจะมีข้อมูลตลาดหมีจริงมาทดสอบและผ่าน cross-asset validation

---

## 15. v3.6 — Bear-Market Data + Short-Side Grid + RL Learning Loop

### 15.1 ข้อมูลตลาดหมีจริง (ปิดข้อจำกัดสำคัญของ v3.2)

`data/btc_bear_2021_2023.json` — BTC/USDT รายวัน 1000 แท่ง (ม.ค. 2021 – ก.ย. 2023,
Binance public API) ครอบคลุมตลาดหมี 2022 เต็มรูปแบบ: peak 67.5k → trough 15.8k (-77%)
โหลดด้วย `load_bear_market()`

**Finding ใหม่ (สำคัญ): config ไม่ transfer ข้าม volatility scale** — config ที่จูนบน
synthetic (ราคา 100, vol ~0.8%/แท่ง) พอวางบน BTC จริง (vol ~5%/แท่ง) จะได้ zone geometry
เพี้ยนสุดขั้ว: levels ราคาติดลบ (-22k), stop ที่ -27k ไม่มีวัน trigger → แทบไม่เทรดเลย
บทเรียน: **ต้อง (re)tune บนข้อมูลที่ volatility scale ตรงกับเป้าเสมอ** (walk-forward v3.2
ปลอดภัยจากปัญหานี้เพราะ re-tune ต่อ fold บนข้อมูลจริงอยู่แล้ว)

Walk-forward บน bear dataset (3 seeds × 12 folds): **ทั้ง Dynamic และ Static แทบไม่เทรด**
(median return 0.00% ทั้งคู่, robust score เท่ากัน -0.0045) — เกณฑ์ที่ลงโทษ DD หนัก
ทำให้ optimizer เลือก "อยู่รอดด้วยการไม่เล่น" ในตลาดหมี ปลอดภัยแต่ไม่ทำกำไร →
motivate ฝั่ง short โดยตรง

### 15.2 Short-Side Grid (`dynamic_grid/short_engine.py`)

`ShortGridEngine` — mirror สมบูรณ์ของ engine ฝั่ง long: sell levels เหนือ center,
TP ต่ำกว่า entry, zone stop อยู่**เหนือ**โซน, trend gate กลับด้าน (ไม่วาง short สวน
trend_up), momentum confirm กลับด้าน (ระงับ fill ช่วง rally spike), consolidation บน
up anomaly, recenter ตามราคาลง — ใช้ DecisionLog vocabulary เดิม ต่อ Virtual Office /
Cognee ได้ทันที

Sanity บน synthetic: downtrend +10.6% (ทิศถูก), uptrend -16.3% (ยังไม่จูน — สมมาตรกับ
long ที่ยังไม่จูนใน downtrend)

**ทดสอบจริงแบบซื่อสัตย์** (`bear_short_demo.py`): จูนบนปี 2021 เท่านั้น (ขาขึ้น+แกว่ง —
เสียเปรียบสำหรับ short) → ทดสอบบน bear 2022 ที่ไม่เคยเห็น (-74%), 3 seeds รายงานครบ:

| | OOS mean return | worst DD | per-seed |
|---|---|---|---|
| LONG Dynamic | -3.94% | 8.83% | -3.1% / -3.4% / -5.3% |
| SHORT Dynamic | **+0.63%** | **0.54%** | +1.7% / +0.2% / +0.0% |

กำไรไม่หวือหวา (config จูนจากปีกระทิงจึง conservative มาก) แต่**ถูกทิศ ปลอดภัย และเป็น
บวกในตลาดที่ long เสียหาย** — ⚠️ ยังไม่รวม funding rate ของ perpetual

### 15.3 RL Learning Loop (`dynamic_grid/rl_agent.py`)

Tabular Q-learning risk governor — แทนกฎมือเขียนของ v3.5 ด้วย policy ที่เรียนรู้เอง
เลือก tabular (12 states × 3 actions) อย่างจงใจ: numpy-only, ตรวจสอบได้ทุกช่อง,
ไม่ overfit ง่ายแบบ neural net บน episode จำกัด

MDP (ประกาศก่อนประเมิน): state = regime(4) × แนวโน้ม equity ใน window(3),
action = global risk scale {0.25, 0.5, 1.0} ทุก 50 แท่ง, reward = Δequity − 2×window DD
(สูตร robust เดิม), train บน seeds 1-2 (96 episodes), **ประเมิน greedy บน held-out
seeds 7/11/13**

**ผล held-out** (`rl_demo.py`, robust score):

| | OFF (fixed) | RULE (v3.5) | RL (learned) |
|---|---|---|---|
| Mean robust score | -0.0383 | -0.0342 | **-0.0230** |
| Mean return | +0.25% | +0.35% | -0.10% |
| Worst DD | 5.68% | 5.36% | **4.23%** |

**คำตัดสินซื่อสัตย์**: RL ชนะชัดตามเกณฑ์ที่ประกาศไว้ (ดีกว่า OFF ~40%, ดีกว่า RULE ~33%)
โดยชนะจากการ**กด DD และ tail risk** — แต่ raw return ติดลบเล็กน้อย (-0.10% vs +0.35%)
ถ้าใครตัดสินด้วย return อย่างเดียว RL แพ้ — เกณฑ์ต้องประกาศก่อน ไม่ใช่เลือกทีหลัง
Policy ที่เรียนได้ตีความง่าย: "อยู่เล็กๆ ไว้ก่อนแทบทุกสภาวะ, เต็มไม้เฉพาะ trend_up ที่
equity กำลังขึ้น" (`results/q_table.json` + `policy_table()` พิมพ์ audit ได้ทุกช่อง)

ข้อจำกัด: ยัง train/ประเมินบน synthetic เท่านั้น — ก่อนใช้จริงต้อง (1) train/validate
กับข้อมูลจริงหลายช่วง (2) ระวัง regime detector เป็น input เดียวของ state

### 15.4 Dual-Side Portfolio (v3.7) — long 75% + short 25% ในพอร์ตเดียว

`make_dual_layers()` (orchestrator.py) — เพิ่ม `engine_cls` ต่อ LayerSpec ทำให้
MemoryOrchestrator คุม engine ต่างชนิดร่วมกันได้: long stack (fast/core/wide, 75%)
+ short layer (25%) — **regime gate ของสองฝั่งเป็น complement กันโดยธรรมชาติ**
(long ไม่ build ใน trend_down, short ไม่ build ใน trend_up) จึงไม่ต้องมี switching rule
น้ำหนัก 75/25 ประกาศล่วงหน้า ไม่ sweep หลังเห็นผล

**ผล (เกณฑ์: robust score, ประกาศก่อนรัน) — dual ชนะทั้ง 3 สนาม:**

| สนามทดสอบ | long-only | dual 75/25 |
|---|---|---|
| A) Synthetic 6 ตลาด × held-out seeds | -0.0342 | **-0.0309** |
| B) Bear จริง 2022 (-74%, unseen) | -3.21% / DD 5.46% | **-1.99% / DD 3.63%** |
| C) Bull จริง 2023-26 (unseen) | +5.50% / DD 10.95% | +3.91% / **DD 8.12%** |

**รายงานสองด้าน**: ใน bull ตลาดขาขึ้น long-only ได้ return ดิบสูงกว่า (+5.50% vs +3.91%)
— dual ชนะบนเกณฑ์ robust เพราะกด DD ได้มากกว่าที่เสีย return; ใน synthetic รายตลาด
dual แพ้ใน sideways/uptrend/regime_switch (short layer จ่ายต้นทุนตอนตลาดขึ้น) แต่ชนะมาก
ใน downtrend/crash/high_vol — สรุป: dual คือการซื้อประกันขาลงด้วยส่วนหนึ่งของกำไรขาขึ้น
สอดคล้องปรัชญาข้อ 1 ทุกประการ

### 15.5 RL + Dual Portfolio — ค้นหา Edge ที่แท้จริง (v3.8) — คำเตือนสำคัญที่สุดในเอกสารนี้

> ⚠️ **ผลลัพธ์นี้เปลี่ยนคำแนะนำก่อนหน้า**: อย่าใช้ Dual RL ทั้งที่มัน "ชนะ" บน 2 ใน 3 สนาม

ต่อยอดจากคำแนะนำเดิม ("เอา RL Governor มาคุม Dual-side portfolio") — `edge_demo.py` train
Q-table บน dual layer stack (long+short) แล้ววัด 3 สนามเดียวกับ v3.7 (synthetic held-out,
bear จริง 2022, bull จริง 2023-26) เทียบ 4 ตัว: long/dual × rule/RL

| สนาม | long rule | long RL | dual rule | dual RL |
|---|---|---|---|---|
| A) Synthetic robust | -0.0342 | -0.0230 | -0.0309 | **-0.0164 (ดีสุด)** |
| B) Bear จริง robust | -0.1413 | -0.1496 (แย่กว่า rule) | -0.0924 | **-0.0895 (ดีสุด)** |
| C) Bull จริง return | **+5.50%** | **-2.72%** | **+3.91%** | **-1.88%** |
| C) Bull จริง robust | -0.1639 | **-0.2383 (แย่สุด)** | -0.1234 | -0.1603 |

### Edge ที่แท้จริงที่พบ: RL synthetic-only เป็นสัญญาณอันตราย ไม่ใช่สัญญาณดี

Dual RL ดูเหมือนชนะทุกตัวถ้าดูแค่ A และ B — แต่ใน**สนาม C (bull จริง) RL พลิกกำไรเป็น
ขาดทุนทั้งคู่**: long rule +5.50% → long RL **-2.72%**, dual rule +3.91% → dual RL **-1.88%**
ไม่ใช่แค่กำไรน้อยลง แต่**ติดลบ**ในตลาดที่ควรได้กำไรชัดเจน

**สาเหตุ (เชื่อมกับ finding เดิมใน v3.6)**: นี่คือบทเรียน "config ไม่ transfer ข้าม
volatility scale" แบบเดียวกัน แต่เกิดกับ **policy ที่เรียนรู้เอง** — Q-table เรียนจาก
state (regime × equity trend) ที่คำนวณบน synthetic price dynamics (ATR ~0.8%/แท่ง)
พอ regime detector ทำงานบน BTC จริง (ATR ~5%/แท่ง) การจำแนก state จึงคลาดเคลื่อน
policy จึงตัดสินใจผิดจังหวะในตลาดจริงที่มันไม่เคยฝึกมา — **RL benchmark บน synthetic
เพียงอย่างเดียวจึงใช้ทำนายผลบนข้อมูลจริงไม่ได้เลย ต่อให้ตัวเลข synthetic ดีแค่ไหน**

### คำแนะนำที่แก้ไขจากเดิม

**เกณฑ์ synthetic held-out ไม่พอสำหรับ RL อีกต่อไป** — ต้องเพิ่ม "held-out บนข้อมูลจริง"
เป็นเงื่อนไขบังคับก่อนเชื่อผล RL ใดๆ (rule-based ยัง transfer ได้ดีกว่าอย่างเห็นได้ชัด —
compare bull: long rule/dual rule ยังเป็นบวกทั้งคู่)

**ข้อสรุปตอนนี้**: **Dual Rule-based (v3.7)** ยังเป็นตัวเลือกที่ปลอดภัยที่สุดสำหรับการ
พิจารณาใช้งานจริง เพราะเป็นตัวเดียวที่ transfer ไปข้อมูลจริงได้สม่ำเสมอทั้ง bear และ bull
— **Dual RL ถูกถอนคำแนะนำ** จนกว่าจะ train ใหม่บนข้อมูลจริง (ไม่ใช่ synthetic) และผ่าน
held-out บนข้อมูลจริงชุดอื่นด้วย

รัน: `python edge_demo.py`

### 15.6 Cross-Asset Router Validation (v3.9) — BTC/ETH/SOL × 1d/4h, ต้นทุนจริง

**เกณฑ์ที่ผู้ใช้ประกาศ**: regime router ต้อง "ลด drawdown โดยไม่ทำลายผลตอบแทน
**ข้ามสินทรัพย์**" จึงจะถือว่า defensive edge มีหลักฐานรองรับ

**Protocol** (`multiasset_demo.py`, `dynamic_grid/market_data.py`):
- 6 ตลาด: BTC/ETH/SOL × 1d (~2.7 ปี) / 4h (~11 เดือน), spot klines จริงพร้อม volume
- ต้นทุนจริง: fee 0.05%/ข้าง + half-spread จาก Corwin-Schultz บน high/low จริง
  (ประมาณการแบบ conservative — สูงกว่า spread จริงของ Binance มาก โดยเฉพาะบน 1d;
  ON/OFF ใช้ต้นทุนชุดเดียวกัน การเปรียบเทียบภายในจึงยุติธรรม แต่ค่า return สัมบูรณ์
  ถูกกดต่ำกว่าจริง) + **funding history จริง 500 events/เหรียญ** (SOL funding ติดลบ
  = long ได้เงิน — texture จริงที่ synthetic ไม่มี)
- จูนบน train 60% โดย router OFF (กันการจูนเข้าข้าง router) → ทดสอบบน test 40%
  เทียบ OFF vs ON (PersistentRegimeDetector 2D + confirm/dwell/hysteresis +
  block_high_vol_entries), **3 seeds ต่อตลาด** (บทเรียน v3.2.1)
- Volume check: exposure สูงสุด ≤ ~0.001% ของ median bar quote volume — fill เป็น
  สัดส่วนจิ๋วของ volume จริง ไม่ต้องมี market-impact model ที่สเกลนี้

**ผล (14 engaged seed-runs จาก 18; 4 runs router ไม่ engage เพราะแทบไม่เทรดใต้ต้นทุนจริง):**

| ตลาด | ผ่าน (engaged seeds) | หมายเหตุ |
|---|---|---|
| BTC/1d | 1/3 | seed 0 router แย่กว่า, seed 1 ดีกว่า, seed 2 เกือบเท่า |
| BTC/4h | **2/3** | ดีสุดในกลุ่ม — DD ลดใน 2 seeds |
| ETH/1d | 1/2 | |
| ETH/4h | 1/3 | |
| SOL/1d | 1/3 | แกว่งสุดขั้ว: seed 0 router เพิ่ม loss เท่าตัว, seed 2 เกือบล้าง loss |
| SOL/4h | n/a | ไม่เทรดพอจะตัดสิน |

### คำตัดสินตามเกณฑ์ที่ประกาศ: **ยังไม่ผ่าน — defensive edge ยังไม่มีหลักฐานรองรับข้ามสินทรัพย์**

รวม 6/14 engaged runs (43%) — ไม่มีตลาดไหนผ่านสม่ำเสมอทุก seed (BTC/4h ใกล้สุดที่ 2/3)
และผลของ router **เล็กกว่า noise ระหว่าง seed ของการจูน** ใน SOL/1d seed เดียวกันของ
router ให้ผลตั้งแต่ "เพิ่ม loss เท่าตัว" ถึง "เกือบล้าง loss" — สรุปว่า ณ ตอนนี้สัญญาณ
ที่วัดได้ของ router บนข้อมูลจริงหลายสินทรัพย์ยัง **แยกไม่ออกจาก noise**

**สิ่งที่ต้องทำก่อนทดสอบซ้ำ**: (1) spread จริงจาก L1 quotes แทน CS estimate (ต้นทุนที่
สูงเกินจริงกดจำนวนเทรดจน router ไม่มีเวทีแสดงผล — 4 จาก 18 runs ไม่ engage เลย)
(2) จูนพารามิเตอร์ router (confirm/dwell) แยกต่อ timeframe (3) เพิ่ม seeds และ
หลาย test-window (4) ลดมิติการจูนฐานเพื่อลด seed variance ที่กลบสัญญาณ

### 15.7 Percentile-Rank Regime — v3.10 (E14) — แก้ root cause ของ E13 ได้จริง

**สมมติฐาน**: E13 ล้มเหลวเพราะ fixed threshold (`m_threshold`, `vol_hi`) ใช้ค่าคงที่
เดียวกันข้าม BTC/ETH/SOL และ 1d/4h ทั้งที่ momentum/vol_ratio ของแต่ละตลาดอยู่คนละสเกล
— ปัญหาเดียวกับ E8/E12 ("config ไม่ transfer ข้าม volatility scale") แค่คนละจุดในระบบ

**`PercentileRegimeDetector`** (`dynamic_grid/regime.py`) — จำแนก regime จาก **percentile
rank ของ momentum/vol_ratio ปัจจุบันเทียบ rolling distribution ของตัวเอง** (default
window 250 แท่ง, เกณฑ์ percentile 85) แทนเทียบค่าคงที่ — scale-invariant โดยธรรมชาติ
ใช้ confirm/dwell/hysteresis เดิมจาก `PersistentRegimeDetector` ทุกอย่าง (inherit)
เพิ่มเฉพาะ config flags: `use_regime_pct`, `regime_pct_window`, `regime_trend_pct`,
`regime_vol_pct` — สร้าง `build_detector(cfg)` factory กลางให้ทั้ง long/short engine
เรียกใช้ร่วมกัน (กันโค้ดซ้ำ)

**ผล (protocol เดียวกับ E13 เป๊ะ — 6 ตลาด × 3 seeds, ต้นทุนจริงชุดเดียวกัน):**

| | Fixed-threshold (E13) | **Percentile-rank (E14)** |
|---|---|---|
| Pass rate | 6/14 (43%) | **10/12 (83%)** |
| BTC/1d, BTC/4h | 1/3, 2/3 | **3/3, 3/3** |

**คำตัดสิน**: ✅ ผ่านเกณฑ์ "pass rate สูงกว่าอย่างชัดเจน" ที่ประกาศไว้ก่อนรัน —
**percentile-rank เป็นตัวเลือกที่แนะนำแทน fixed-threshold** สำหรับ regime router

**ข้อสังเกตตรงๆ**: (1) "ผ่าน" ตามกฎ (ดีขึ้นกว่า baseline) ≠ "ปลอดภัยพอใช้จริง" —
BTC/1d ผ่านทุก seed แต่ DD สัมบูรณ์ยังสูง 15-20% (2) ETH/1d กลับแย่ลง — ไม่ใช่ยาวิเศษ
ทุกกรณี (3) SOL/4h ยังไม่เทรดเหมือนเดิม — ต้องมี **edge filter ก่อนเข้า** (candidate
ถัดไป, บันทึกไว้ใน VALIDATION_LOG) รายละเอียดเต็ม: `docs/VALIDATION_LOG.md` § E14

รัน: `python percentile_regime_demo.py` | ผลดิบ: `results/percentile_regime_e14.csv`

## 16. Changelog

- **v3.10 (2026-07-11)**: Percentile-rank regime detector — แก้ root cause ของ E13
  (fixed threshold ไม่ scale-invariant) ด้วย `PercentileRegimeDetector` (จำแนกจาก
  percentile rank เทียบ rolling distribution ของตัวเอง) — protocol เดียวกับ E13 เป๊ะ:
  pass rate เพิ่มจาก 43%→**83%** (6/14→10/12 engaged runs) ผ่านเกณฑ์ที่ประกาศไว้
  ("ต้องดีกว่าอย่างชัดเจน") — กลายเป็น router ที่แนะนำแทน fixed-threshold แต่ยังมีช่องว่าง
  (SOL/4h ไม่เทรด, ETH/1d ไม่ดีขึ้น) ดูหัวข้อ 15.7, `percentile_regime_demo.py`
- **v3.9 (2026-07-11)**: Cross-asset router validation — BTC/ETH/SOL × 1d/4h, ต้นทุนจริง
  (spread CS-estimate + funding history จริง + volume check), 3 seeds/ตลาด —
  **เกณฑ์ของผู้ใช้ยังไม่ผ่าน**: router ผ่าน 6/14 engaged runs, ไม่มีตลาดที่ผ่านทุก seed,
  ผลของ router เล็กกว่า seed noise; `multiasset_demo.py`, `dynamic_grid/market_data.py`
  ดูหัวข้อ 15.6
- **v3.8 (2026-07-09)**: ค้นหา edge จริงโดยเอา RL Governor คุม Dual portfolio —
  **พบว่า RL ที่ train บน synthetic ล้วนพลิกกำไรเป็นขาดทุนบน bull ตลาดจริง** (long RL
  +5.50%→-2.72%, dual RL +3.91%→-1.88%) แม้จะชนะบน synthetic held-out และ bear จริง
  — ถอนคำแนะนำ Dual RL, ยึด **Dual Rule-based (v3.7)** เป็นตัวเลือกปลอดภัยสุดแทน
  จนกว่าจะ train RL ใหม่บนข้อมูลจริง; `edge_demo.py` ดูหัวข้อ 15.5
- **v3.7 (2026-07-09)**: Dual-side portfolio — `LayerSpec.engine_cls` (mixed engine ต่อ layer),
  `make_dual_layers()` long 75% + short 25% ใต้ MemoryOrchestrator เดียว; ชนะ long-only
  บนเกณฑ์ robust ทั้ง synthetic held-out (-0.0309 vs -0.0342), bear จริง (-1.99%/DD 3.63
  vs -3.21%/DD 5.46) และ bull จริง (robust -0.1234 vs -0.1639 แม้ return ดิบต่ำกว่า);
  `dual_demo.py` ดูหัวข้อ 15.4
- **v3.6 (2026-07-09)**: (1) ข้อมูลตลาดหมีจริง 2021-2023 + finding "config ไม่ transfer
  ข้าม volatility scale" (2) `ShortGridEngine` — ทดสอบ OOS บน bear จริง: +0.63%/DD 0.54%
  ขณะ long -3.94%/DD 8.83% (3) RL tabular Q-learning governor — ชนะทั้ง fixed และ
  rule-based บน held-out robust score (-0.0230 vs -0.0342/-0.0383) ด้วยการกด tail risk
  แลก return; scripts: `bear_short_demo.py`, `rl_demo.py` ดูหัวข้อ 15
- **v3.5 (2026-07-08)**: Memory-loop orchestrator (`dynamic_grid/orchestrator_agent.py`:
  `MemoryOrchestrator` อ่าน shared DecisionLog ทุก 200 แท่ง → cut/restore risk budget ตามกฎ
  ที่ประกาศไว้, log intervention กลับเข้า log เดียวกัน) — A/B ชนะ fixed weights ตามเกณฑ์
  robust score (−0.0342 vs −0.0383) ดีขึ้นหลักๆ ใน downtrend; กฎเวอร์ชันแรก threshold=2/50แท่ง
  ตายเชิงกลไก (เป็นไปไม่ได้เพราะ cooldown) แก้ก่อนดูคะแนน ดูหัวข้อ 7D; `orchestrator_demo.py`;
  `logging_demo.py` ใช้ MemoryOrchestrator; Virtual Office เพิ่มโต๊ะ orchestrator + icons
- **v3.4 (2026-07-08)**: Virtual Office front-end (`virtual_office.html`) — single-file
  HTML5/JS/canvas app อ่าน `decision_events.jsonl` มา animate สถานะ agent ต่อ bar
  (office floor + shared-memory hub + price wall + decision feed + playback) ทดสอบจริง
  ผ่าน browser แล้ว ดูหัวข้อ 7D
- **v3.3 (2026-07-08)**: เพิ่ม structured decision logging (`dynamic_grid/event_log.py`:
  `DecisionEvent`/`DecisionLog` → JSONL + knowledge statements, `logging_demo.py`) เป็นรากฐาน
  ของ MAS / Cognee memory / Virtual Office — opt-in (logger=None reproduce ผลเดิมทุกไบต์),
  แต่ละ layer log เป็น named agent ลง shared log + Cognee bridge
  (`dynamic_grid/cognee_adapter.py`: `push_log`/`push_findings`/`recall`, `cognee_demo.py`)
  — cognee เป็น optional dep, feature-detect API version, มีชุด PROJECT_FINDINGS
  (negative results) พร้อม push ดูหัวข้อ 7D
- **v3.2.1 (2026-07-08)**: แก้ overfitting-to-regime ที่พบใน walk-forward ด้วย sub-window
  robust scoring (`_optimize_on_window` ให้คะแนนข้าม 4 sub-window ของ train แทนก้อนเดียว
  ดูหัวข้อ 13) — ผลจาก aggregate 5 seeds × 12 folds: **ลด tail risk ได้จริงมาก**
  (worst maxDD ของ Static เอง 21.47%→3.56%) **แต่ไม่พลิกข้อสรุปหลัก** — Static ยังชนะ Dynamic
  ทั้ง mean/median return บน BTC/USDT จริง บทเรียนสำคัญคู่กัน: ผลรอบแรกที่ดูเหมือน "Dynamic ชนะ"
  มาจาก seed เดียวที่บังเอิญดี — ต้อง aggregate หลาย seed ก่อนสรุปเสมอ
- **v3.2 (2026-07-08)**: เพิ่ม walk-forward validation บนข้อมูลจริง (`dynamic_grid/real_data.py`,
  `dynamic_grid/walk_forward.py`, `walk_forward_demo.py`) — ผลลัพธ์เบื้องต้น (ก่อนแก้ v3.2.1):
  Static ชนะ Dynamic ในข้อมูล BTC/USDT จริงทุกตัวชี้วัด เพราะ optimizer overfit ต่อ regime ของ
  training window เดียว เพิ่มเพดาน exposure รวมข้าม layer
  (`MultiLayerOrchestrator(max_gross_exposure=...)`, หัวข้อ 7.5b) — กลไกทำงานถูกต้องแต่แทบไม่ fire
  ด้วย layer weights ปัจจุบันเพราะ layer ยังสัมพันธ์กันสูง
- **v3.1 (2026-07-07)**: State-based Momentum Confirmation ที่ชั้น fill
  (`momentum_confirm`, `entry_m_block` — รับเข้า config แนะนำหลังชนะ ablation
  ด้วย robust score บน held-out seeds), ตัวชี้วัดเชิงลึก CVaR 5% / Profit Factor /
  Recovery Factor ใน `BacktestResult`, สคริปต์ `ablation_momentum.py`
- **v3 (2026-07-07)**: เพิ่ม `orchestrator.py` (`MultiLayerOrchestrator`, `make_layers`),
  รองรับ backtest engine-agnostic (`run_backtest_engine`), เดโม `multilayer_demo.py`,
  บันทึกผล single vs multi-layer + ข้อจำกัดที่ทราบ (หัวข้อ 7)
- **v2 (2026-07-06)**: เพิ่ม RegimeDetector + regime-adaptive risk/spacing/gating,
  ablation test (`compare_versions.py`)
- **v1 (2026-07-06)**: ระบบแรก — ATR spacing, risk per zone, zone stop + cooldown,
  trend filter, anomaly consolidation, synthetic scenarios 6 แบบ, robust optimizer
