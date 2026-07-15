# Dynamic Grid Trading System

> **เป้าหมายระบบ (ปรับใหม่):** พัฒนาไปสู่ศูนย์กลางการปฏิบัติการลงทุนหลายแพลตฟอร์ม
> ที่มี P/L ledger และการกระทบยอดตรวจสอบย้อนหลังได้ครบถ้วน เพื่อสร้าง track record
> ก่อนยกระดับสู่ private fund อย่างถูกต้องตามกฎหมาย — เริ่มจาก read-only และ paper
> trading เท่านั้น

📕 **Roadmap: Multi-Platform → Private Fund Readiness: [docs/PRIVATE_FUND_ROADMAP.md](docs/PRIVATE_FUND_ROADMAP.md)**
— เป้าหมาย, data/P&L model, connector, reconciliation, risk control และ governance

ระบบเทรดกริดแบบไม่คงที่ (Adaptive/Dynamic Grid) — ต้นแบบที่รันได้จริง สร้างตามแนวคิด:
กริดที่ปรับ Grid Construction ตามพฤติกรรมราคา, จำกัด Risk per Zone,
กำหนด Order Distance ด้วย Volatility, รวบโซน/สะสมทบเมื่อเจอ Price Anomaly
และใช้ AI/Optimization ในการ fine-tune พารามิเตอร์บน synthetic data หลายแบบจำลอง

ต้องการแค่ **Python 3.10+ และ numpy** เท่านั้น

> ⚠️ **อ่านก่อน (v3.8)**: RL Governor ที่ train บน synthetic เพียงอย่างเดียว **พลิกกำไรเป็น
> ขาดทุนบนตลาดกระทิงจริง** (+5.50% → -2.72%) แม้จะชนะบน synthetic benchmark ทุกตัว —
> **ห้ามใช้ RL variant เทรดเงินจริง**, ใช้ **Dual Rule-based (v3.7)** แทนซึ่ง transfer ไป
> ข้อมูลจริงได้สม่ำเสมอกว่า รายละเอียดที่ [docs/SYSTEM_SPEC.md](docs/SYSTEM_SPEC.md) หัวข้อ 15.5
> — **ทั้งระบบยังไม่ควรใช้เทรดเงินจริงโดยตรง**

📗 **สมุดบันทึกหลักฐานการทดสอบ: [docs/VALIDATION_LOG.md](docs/VALIDATION_LOG.md)**
— ทุกการทดลอง E1–E14 ในรูปแบบ คำถาม→เกณฑ์→ผล→คำตัดสิน→คำสั่งทำซ้ำ + กฎเหล็ก 8 ข้อ

📙 **Handoff สำหรับทำงานต่อ (Cursor หรือ agent อื่น): [docs/HANDOFF_CURSOR.md](docs/HANDOFF_CURSOR.md)**
— สถานะปัจจุบัน, integration gap ที่ต้องปิดก่อน, งานถัดไปเรียงลำดับความคุ้มค่า, กติกาบังคับ

🧭 **Agent Stack (Fable 5 + GPT-5.6 doctrine): [docs/AGENT_STACK.md](docs/AGENT_STACK.md)**
— constitution (`AGENTS.md`), routing, deterministic gate, advisor inversion, heartbeat loop

📘 **เอกสารระบบฉบับละเอียด (v3.10): [docs/SYSTEM_SPEC.md](docs/SYSTEM_SPEC.md)**
— สถาปัตยกรรม, Regime Detection, Multi-Layer Orchestrator, Walk-Forward บนข้อมูลจริง, ผลทดสอบ, config แนะนำ

```
python compare_versions.py  # ablation: v1 vs v2 (regime-adaptive)
python validate_v2.py       # held-out validation ของ regime config
python multilayer_demo.py   # เทียบ single-layer vs multi-layer (v3)
python ablation_momentum.py # ablation: momentum confirmation + deep metrics (v3.1)
python walk_forward_demo.py # walk-forward บนข้อมูล BTC/USDT จริง 1000 แท่ง (v3.2)
python logging_demo.py      # structured decision log → JSONL + knowledge (v3.3, รากฐาน MAS/Cognee/Virtual Office)
python cognee_demo.py       # push log + findings เข้า Cognee knowledge graph → recall (v3.3, ต้อง uv pip install cognee)
python -m http.server 8931  # แล้วเปิด http://localhost:8931/virtual_office.html — Virtual Office animation (v3.4)
python orchestrator_demo.py # A/B: memory-loop orchestrator (อ่าน log → ปรับ risk budget) vs fixed weights (v3.5)
python bear_short_demo.py   # Long vs Short grid บนตลาดหมี 2022 จริง (-74%) จูนเฉพาะปี 2021 (v3.6)
python rl_demo.py           # RL: train Q-learning governor + ประเมิน held-out vs fixed/rule-based (v3.6)
python dual_demo.py         # dual-side portfolio (long 75% + short 25%) vs long-only บน synthetic+bear+bull (v3.7)
python edge_demo.py         # RL คุม dual portfolio: ชนะ synthetic+bear แต่พังบน bull จริง (v3.8, สำคัญ — อ่านก่อนใช้ RL)
python multiasset_demo.py   # cross-asset router validation: BTC/ETH/SOL × 1d/4h ต้นทุนจริง — ยังไม่ผ่านเกณฑ์ (v3.9)
python percentile_regime_demo.py  # percentile-rank regime แก้ปัญหา v3.9: pass rate 43%→83% (v3.10)
python regime_execution_demo.py   # v4: legacy vs persistent 2D regime ภายใต้ conservative execution
python regime_switch_edge_demo.py # v4: fixed dual vs long/short regime router, train/test แยกกัน
python agent/executor_advisor.py  # Advisor inversion: Sonnet/Sol driver + Fable advisor (≤3 consults)
python agent/router.py "..."      # offline difficulty → cheap/mid/frontier_in_loop
powershell -File gate/verify.ps1  # deterministic ship gate (final vote)
```

```
python run_demo.py          # เปรียบเทียบ Static vs Dynamic + optimize พารามิเตอร์
python run_demo.py --fast   # เปรียบเทียบอย่างเดียว (ไม่ optimize)
```

ผลลัพธ์ถูกบันทึกลงโฟลเดอร์ `results/` เป็น CSV

## แนวคิด → โค้ด

| แนวคิดในโน้ต | จุดที่ implement |
|---|---|
| Order Distance ตาม Volatility | `grid_engine.py` — spacing = `atr_mult * ATR` ณ เวลาสร้างโซน (`indicators.py`) |
| โซนไม่ fix / ปรับตามราคา | `_build()` สร้างโซนใหม่เมื่อราคาหลุดโซน (ขึ้น = recenter ตาม, ลง = ตัดขาดทุนทั้งโซน + cooldown) |
| Risk per Zone | `risk.py` — ขาดทุน worst-case ของทั้งโซนถูกจำกัดที่ `risk_per_zone` ของ equity แบ่ง budget เท่ากันต่อ level |
| แก้ปัญหาโดนลาก / DD 80-90% | zone stop + cooldown + trend filter (`trend_k`: ไม่วางกริดสวนขาลงแรงใต้ EMA) |
| รวบโซน/สะสมทบ Order (Price Anomaly) | `_consolidate()` — เมื่อแท่งเคลื่อน > `anomaly_z * ATR` รวบ level ที่ยังไม่ fill เป็นครึ่ง แต่ size ต่อไม้ใหญ่ขึ้น |
| ทดสอบกับ synthetic data หลายแบบจำลอง | `synthetic.py` — 6 scenario: sideways, uptrend, downtrend, crash, regime_switch, high_vol |
| AI Optimization fine-tune Zone / Order distance / RPT | `optimize.py` — random search ข้ามทุก scenario พร้อมกัน ให้คะแนนแบบ robust (mean − penalty ความไม่สม่ำเสมอ − 2×DD) |

## โครงสร้าง

```
dynamic_grid/
  synthetic.py    เครื่องกำเนิดข้อมูล OHLC สังเคราะห์ (GBM, OU, jump, regime-switch)
  indicators.py   ATR (Wilder) + ตัวตรวจ Price Anomaly
  risk.py         position sizing แบบ Risk per Zone
  grid_engine.py  DynamicGridEngine + StaticGridEngine (baseline เปรียบเทียบ)
  regime.py       RegimeDetector — จำแนกสภาวะตลาด 4 โหมด (v2)
  orchestrator.py MultiLayerOrchestrator + make_layers — คุมหลาย engine คนละสเกล (v3)
  backtest.py     backtester รายแท่ง + metrics (return, maxDD, MAR, CVaR, Profit Factor, Recovery Factor)
  optimize.py     random-search optimizer ข้ามหลาย scenario
  real_data.py    loader ข้อมูล OHLC จริง (Binance klines JSON)
  walk_forward.py walk-forward: optimize บน train window → ทดสอบบน test window ถัดไป (v3.2)
run_demo.py           เดโม end-to-end (single-layer)
multilayer_demo.py    เดโม single-layer vs multi-layer
walk_forward_demo.py  เดโม walk-forward บนข้อมูล BTC/USDT จริง
data/btc_binance_1d.json  ข้อมูลจริง 1000 แท่ง (ดาวน์โหลดจาก Binance public API)
```

## กลไกหลักของ DynamicGridEngine (ต่อ 1 แท่ง)

1. อัปเดต ATR / EMA / ตรวจ anomaly
2. Take-profit ไม้ที่ราคาถึง TP (= `tp_mult × spacing` เหนือราคาเข้า) แล้ว re-arm level เดิม
3. Fill คำสั่งซื้อของ level ที่ราคา Low กวาดถึง
4. ถ้าราคาหลุด **zone stop** → ตัดขาดทุนทุกไม้ทันที (ขาดทุนรวม ≤ `risk_per_zone`)
   แล้วพัก `cooldown_bars` แท่ง ก่อนพิจารณาสร้างโซนใหม่
5. ถ้าเจอ **anomaly ขาลง** → รวบ level ที่เหลือ (ครึ่งจำนวน, size ใหญ่ขึ้น, ลึกลง)
6. ถ้าราคาวิ่งพ้นขอบบน → สร้างโซนใหม่ตามราคา (spacing ใหม่จาก ATR ปัจจุบัน)
7. โซนใหม่จะสร้างได้ก็ต่อเมื่อผ่าน **trend filter** (close ≥ EMA − `trend_k × ATR`)

## พารามิเตอร์ (DynamicGridConfig)

| พารามิเตอร์ | ค่าเริ่มต้น | ความหมาย |
|---|---|---|
| `levels` | 6 | จำนวน buy level ต่อโซน |
| `atr_mult` | 1.5 | order distance = atr_mult × ATR |
| `risk_per_zone` | 0.04 | ขาดทุนสูงสุดต่อโซน (สัดส่วน equity) |
| `stop_mult` | 1.0 | ระยะ zone stop ใต้ level ล่างสุด (เท่าของ spacing) |
| `shift_trigger` | 2.0 | recenter เมื่อราคาพ้นขอบบน (เท่าของ spacing) |
| `anomaly_z` | 3.0 | เกณฑ์ Price Anomaly (เท่าของ ATR) |
| `consolidation_scale` | 1.0 | ตัวคูณ size ตอนรวบโซน |
| `cooldown_bars` | 20 | จำนวนแท่งพักหลังโดน zone stop |
| `tp_mult` | 1.0 | ระยะ TP (เท่าของ spacing) |
| `trend_k` | 2.0 | ความลึกใต้ EMA ที่ยังยอมสร้างโซน (เท่าของ ATR) |
| `fee_rate` | 0.0005 | ค่าธรรมเนียมต่อ notional ต่อข้าง |

## สิ่งที่ผลทดสอบแสดง

- **Static grid** (โซนคงที่ ไม่มี stop): กำไรดีใน sideways แต่ downtrend โดนลาก
  drawdown 55–77% — พฤติกรรมคลาสสิกของกริดถั่วเฉลี่ยไม่จำกัดความเสี่ยง
- **Dynamic grid**: ยอมเสียกำไรบางส่วนใน sideways แลกกับการจำกัด drawdown
  ทุก scenario ให้อยู่ระดับหลักหน่วยเปอร์เซ็นต์ — "อยู่รอด" ในตลาดที่เลวร้ายที่สุด
- Optimizer หาชุดพารามิเตอร์เดียวที่ **ต้องรอดทั้ง 6 ตลาดพร้อมกัน**
  (ไม่ overfit กับตลาดใดตลาดหนึ่ง)

## Multi-Layer Grid (v3)

`MultiLayerOrchestrator` รัน `DynamicGridEngine` 3 ชุดพร้อมกันคนละสเกลราคา
(fast/core/wide) แบ่ง equity/risk budget ตามน้ำหนัก — แต่ละ layer มี zone stop
/ cooldown / regime gate ของตัวเองครบ ผลทดสอบ (3 seeds × 6 scenario):
**ลด max drawdown ได้ทุก scenario (12–20%)** แลกกับ return เฉลี่ยที่ลดลงราวครึ่งหนึ่ง
(+0.25% vs +0.50%) — trade-off ตรงปรัชญาระบบ (robustness ก่อน return)
รายละเอียดเต็มดูที่ [docs/SYSTEM_SPEC.md](docs/SYSTEM_SPEC.md) หัวข้อ 7

```python
from dynamic_grid import DynamicGridConfig, MultiLayerOrchestrator, make_layers, run_backtest_engine

layers = make_layers(DynamicGridConfig(...))   # สร้าง 3 layer จาก config เดียว
orch = MultiLayerOrchestrator(layers)
result = run_backtest_engine(ohlc, orch)       # ใช้ backtester เดิมได้ทันที
```

## Walk-Forward บนข้อมูลจริง (v3.2 / v3.2.1) — ผลลัพธ์สำคัญที่สุดในเอกสารนี้

รันบน BTC/USDT รายวันจริง 1000 แท่ง (Binance, ต.ค. 2023 – ก.ค. 2026) ด้วย protocol
train 250 วัน → optimize → test 60 วันถัดไป (ไม่เห็นตอน optimize) → เลื่อนหน้าต่าง

รอบแรก (v3.2) optimizer จูนกับ train ทั้งก้อนเดียว → Static ชนะ Dynamic ทุกตัวชี้วัด
สาเหตุ: train เป็นขาขึ้นแรง +142.6% → optimizer เลือกพารามิเตอร์ที่รันยาวไม่หยุด → test เจอ
ปรับฐาน -8.4% Dynamic โดน zone stop พลาดการเด้งกลับที่ Static ถือยาวเก็บได้เต็มๆ

แก้ด้วย **sub-window robust scoring** (v3.2.1) — ให้คะแนน optimizer ข้าม 4 sub-window ของ
train แทนก้อนเดียว (สูตรเดียวกับ robust score ของ synthetic optimizer) ผล aggregate จาก
**5 seeds × 12 folds = 60 fold-runs** (ไม่ใช่ seed เดียว):

| | OLD (train ก้อนเดียว) | NEW (sub-window) |
|---|---|---|
| Dynamic mean / median return | +0.81% / +1.15% | +0.57% / +0.47% |
| Static mean / median return | +1.83% / +0.53% | +1.32% / **+0.03%** |
| Static worst maxDD | **21.47%** | **3.56%** |

**คำตัดสินที่ซื่อสัตย์**: sub-window fix ลด tail risk ได้จริงมาก (worst maxDD ของ Static เอง
ลดจาก 21.47% → 3.56%) แต่**ไม่พลิกข้อสรุปหลัก** — Static ยังชนะ Dynamic ทั้ง mean/median
return บนข้อมูลจริงชุดนี้ ผลรอบแรกที่ดูเหมือน "Dynamic ชนะ" มาจาก seed เดียวที่บังเอิญดี —
บทเรียนสำคัญคือต้อง aggregate หลาย seed ก่อนสรุปเสมอ รายละเอียดเต็มที่
[docs/SYSTEM_SPEC.md](docs/SYSTEM_SPEC.md) หัวข้อ 13

## เพดาน Exposure รวมข้าม Layer (v3.2)

`MultiLayerOrchestrator(layers, max_gross_exposure=0.5)` — เลื่อนการสร้างโซนใหม่ของ layer
ที่ว่างอยู่ ถ้า exposure รวมทุก layer เกินเพดาน กลไกทำงานถูกต้อง (ยืนยันแล้ว) แต่แทบไม่ fire
กับ layer weights ปัจจุบันเพราะ 3 layer ใช้ regime gate ร่วมกัน มักเปิด/ปิดพร้อมกัน — เป็น
safety net ไว้สำหรับอนาคตมากกว่าจะเปลี่ยนผลบน default config วันนี้

## แนวทางต่อยอด (ยังไม่ implement)

- **เพิ่ม n_iter ของ walk-forward optimizer** (ตอนนี้ 60) — ผลยังไวต่อ seed มาก
- หาข้อมูลจริงที่มีตลาดหมีเต็มรูปแบบ + ทดสอบ cross-asset ก่อนสรุปว่า Dynamic ใช้ได้จริง
  (BTC 1000 แท่งที่มีคือกระทิงยาว+ปรับฐานเบา ยังไม่มีตลาดหมีจริงให้ Dynamic ได้แสดงจุดแข็ง)
- Optimize น้ำหนัก/สเกลของ layer ด้วย random search เต็มรูปแบบ
- Learning loop / RL: ให้ policy เลือกปรับ `atr_mult`, `trend_k`, `risk_per_zone` ตาม regime ที่ตรวจจับได้ แทนค่าคงที่
- ฝั่ง short grid สำหรับตลาดขาลง (ปัจจุบันเป็น long-accumulation อย่างเดียว)

> ⚠️ ระบบนี้เป็นต้นแบบเพื่อการศึกษา walk-forward ล่าสุด (v3.2.1) แก้ overfitting-to-regime
> ได้บางส่วน — ลด tail risk ได้จริงแต่ Static ยังชนะ Dynamic บนข้อมูลจริงชุดนี้ **ยังไม่ควรนำ
> ไปเทรดเงินจริง** จนกว่าจะมีข้อมูลตลาดหมีจริงและผ่าน cross-asset validation ยังไม่รวม
> slippage จริง, funding, partial fill ด้วย
