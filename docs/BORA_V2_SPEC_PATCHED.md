# BORA V2

## Bitcoin Order-flow Regime & Absorption Strategy

> Development Specification สำหรับนำไปพัฒนา Backtest, Quant Strategy,
> Paper Trading และ AI/ML ต่อ

## 1. Objective

สร้างระบบ Quant/Order Flow สำหรับ BTC/ETH Futures ที่ไม่ได้ตัดสินใจจาก
Candlestick หรือ Indicator เพียงอย่างเดียว แต่พยายามตอบว่า:

> **เมื่อมีแรงซื้อ/ขายจำนวนมากเข้าตลาด ราคา Response ต่อแรงนั้นอย่างไร และเกิดใน
> Market State/Location แบบไหน?**

Core concept:

``` text
Market State
     ↓
Location
     ↓
Order Flow
     ↓
Price Response
     ↓
Absorption / Continuation
     ↓
Confirmation
     ↓
Risk Gate
     ↓
Execution
```

หลักสำคัญ:

``` text
Aggression ≠ Control

Buy เยอะ ≠ Long
Sell เยอะ ≠ Short

ต้องดูว่า Aggression
สามารถ Move Price ได้จริงหรือไม่
```

## 2. Initial Market Scope

``` text
Market      BTCUSDT Perpetual
Exchange    Binance Futures
TF          5m

Research TF
1m / 5m

Period
2020–2026
```

เมื่อ BTC model stable แล้วให้ทดสอบ `ETHUSDT` เพื่อดูว่า edge เป็น BTC-specific
หรือ generalizable

## 3. Public Data Sources

Primary source: Binance Public Data --- https://data.binance.vision/

Official repository/documentation:
https://github.com/binance/binance-public-data

ข้อมูลหลัก: - Klines - AggTrades - Trades - Funding

Kline fields ที่ใช้: - Open / High / Low / Close - Volume / Quote Volume -
Number of Trades - Taker Buy Base Volume - Taker Buy Quote Volume

AggTrades fields ที่ใช้: - Price - Quantity - Timestamp - Buyer Maker

ใช้ AggTrades เพื่อสร้าง Big Trade/Bubble ใน Phase หลัง

## 4. Data Quality Gate

**ห้าม Backtest ก่อนผ่าน Data Quality**

ตรวจ: - Missing Timestamp - Duplicate Timestamp - Duplicate Trade -
Trade ID Gap - Missing Candle - Invalid OHLC - Zero/Negative Volume -
Abnormal Volume - BuyerMaker abnormality - Data discontinuity

สถานะ: - `VALID` - `WARNING` - `INVALID`

### INVALID Policy

``` text
Bad Dataset
      ↓
Mark INVALID
      ↓
Exclude
      ↓
ไม่ interpolate
ไม่ forward-fill order flow
ไม่สร้าง synthetic Delta
      ↓
ใช้เดือนใกล้เคียงเป็น sample เพิ่ม
```

เช่น June เสีย ให้พิจารณา May → July → April → August

**ห้ามนำข้อมูลเดือนอื่นมาเปลี่ยน timestamp เป็นเดือนที่เสีย** เดือนที่เสียต้องถือเป็น
`NO DATA` เพื่อรักษา chronology ของ Walk-forward test

### Vendor Lock

**ล็อกผู้ให้ข้อมูลไว้ตัวเดียวตั้งแต่แท่งแรก และบันทึกว่าเป็นใคร**

``` text
ทุกตัวเลขที่รายงาน
ต้องมีชื่อ vendor + วันที่ดึง
ติดอยู่ด้วยเสมอ

ห้ามผสม vendor ในชุดเดียวกัน
ห้ามเปลี่ยน vendor กลางการศึกษา
```

Data Quality Gate ข้างบนตรวจว่าข้อมูล **ภายในชุดหนึ่ง** สอดคล้องกัน — มันตรวจไม่ได้ว่า
**สองชุดที่ผ่านทั้งคู่ จะให้คำตอบเดียวกันหรือไม่**

### Cross-Vendor Gate — เป็นด่าน ไม่ใช่เรื่องรอง

เมื่อกลยุทธ์ผ่านด่าน 1–5 ของ §38 แล้ว **ต้องรันซ้ำทั้งชุดบน vendor ที่สอง**
ก่อนลงทุนกับ Phase 3 ขึ้นไป

``` text
รันซ้ำบน vendor ที่ 2
        ↓
เครื่องหมายของผลตรงกันไหม
        ↓
ไม่ตรง → edge ขึ้นกับคนบันทึกราคา
         ไม่ใช่ขึ้นกับตลาด
        ↓
        หยุด
```

**หลักฐานว่าเรื่องนี้ไม่ใช่ทฤษฎี**: กลยุทธ์ที่ผ่านการตรวจสอบมา 15 การทดลอง
ถูกรันบนคู่เหรียญเดิม หน้าต่างเดิม แต่เปลี่ยน vendor — ผลของเหรียญหนึ่ง
**พลิกจาก +34.14 R เป็น −4.64 R** · ข้อมูลทั้งสองชุดผ่าน Data Quality Gate

``` text
Quality Gate ผ่าน  ≠  ข้อมูลชุดนั้นให้คำตอบเดียวกัน
```

ยิ่งกับ order flow ยิ่งสำคัญ: `TakerBuyQuoteVolume` เป็นตัวเลขที่ exchange
รายงานเอง ไม่ใช่ราคาที่หลายแหล่งเห็นตรงกัน — **การเปลี่ยน vendor เปลี่ยนทั้ง
Delta, CVD, Delta_Z และ AbsorptionScore พร้อมกัน**

## 5. Core Order Flow Calculation

### Buy Volume

``` text
BuyVolume = TakerBuyQuoteVolume
```

### Sell Volume

``` text
SellVolume = QuoteVolume - TakerBuyQuoteVolume
```

### Delta

``` text
Delta = BuyVolume - SellVolume
```

ตัวอย่าง:

``` text
Buy  = $80M
Sell = $120M
Delta = -$40M
```

หมายถึง aggressive seller มากกว่า buyer

## 6. CVD

Cumulative Volume Delta:

``` text
CVD(t) = CVD(t-1) + Delta(t)
```

ไม่ใช้ CVD เป็น Buy/Sell signal ตรง ๆ แต่สนใจ divergence

### Bullish Divergence

``` text
CVD → New Low
Price → Higher Low / Equal Low
```

แปลว่า aggressive selling เพิ่ม แต่ประสิทธิภาพในการกดราคาลดลง

### Bearish Divergence

``` text
CVD → New High
Price → Lower High / Equal High
```

## 7. Normalize Order Flow

ห้ามใช้ threshold ตายตัว เช่น `Delta < -$20M` เพราะ market scale
เปลี่ยนตามเวลา

ใช้ Rolling Z-score:

``` text
Delta_Z =
(Delta - RollingMean(Delta))
───────────────────────────
RollingSTD(Delta)
```

Initial window = 100 bars

ทดสอบ window: - 50 - 100 - 200 - 500

Extreme Flow candidates: - `|Z| > 1.5` - `|Z| > 2.0` - `|Z| > 2.5` -
`|Z| > 3.0`

และ percentile: - 90 - 95 - 97 - 99 - 99.5

## 8. Price Impact

หัวใจของ BORA คือการตอบว่า **เงินจำนวนมากเข้ามาแล้ว Move Price ได้แค่ไหน**

ตัวอย่าง normalized:

``` text
PriceImpact =
|Close - Open|
──────────────
ATR
```

สามารถพัฒนาต่อเป็น `DirectionalImpact` เพื่อแยกผลตามทิศทาง Delta

## 9. Absorption Engine

Core hypothesis:

> Extreme aggressive flow + Low price impact = Potential Absorption

Basic formula:

``` text
FlowIntensity = abs(Delta_Z)

PriceImpact =
abs(Return) / ATR_Normalized

AbsorptionScore =
FlowIntensity / (PriceImpact + ε)
```

Initial `ε = 0.10` แต่ต้อง backtest ไม่ถือว่าเป็นค่าที่ดีที่สุด

## 10. Sell Absorption

Candidate Long:

``` text
Delta_Z <= -2
AND
SellVolume >= 95 percentile
AND
DownwardPriceImpact < 0.30 ATR
AND
Close >= Low + 50% ของ candle range
```

มี sell aggression สูงมาก แต่ราคาปิดกลับขึ้น → Potential absorption

## 11. Buy Absorption

กลับด้าน:

``` text
Delta_Z >= +2
AND
BuyVolume >= 95 percentile
AND
UpwardPriceImpact < 0.30 ATR
AND
Close อยู่ lower portion ของ candle
```

→ Potential Short

## 12. Flow Efficiency

``` text
FlowEfficiency =
DirectionalPriceMovement / AggressiveFlow
```

High efficiency: - Sell เยอะ + Price ลงแรง → Sellers control

Low efficiency: - Sell เยอะ + Price แทบไม่ลง → Possible Absorption

## 13. Flow Velocity / Acceleration

อย่าดู Delta bar เดียว ให้คำนวณ: - Delta Velocity - Delta Acceleration

ตัวอย่าง:

``` text
-1M
-2M
-4M
-8M
= Selling accelerating
```

อาจเป็น Continuation

``` text
-8M
-5M
-3M
-1M
= Selling decelerating
```

อาจเป็น Exhaustion

## 14. Location Engine

**Signal ห้าม Trade กลาง nowhere**

Location candidates: - VAH / VAL / POC - LVN / HVN - VWAP / VWAP
deviation - Previous Day High / Low - Session High / Low - Swing High /
Low

Location Score: `0–100`

ตัวอย่าง:

``` text
Absorption = 98 percentile
Location Score = 20
→ NO TRADE
```

แต่:

``` text
Absorption = 98
Location = VAL + Previous Low
→ High Quality Candidate
```

## 15. Market Regime Engine

แบ่ง: - `TREND_UP` - `TREND_DOWN` - `BALANCE` - `HIGH_VOL` - `LOW_VOL` -
`STRESS` - `POST_LIQUIDATION`

Features: - ATR percentile - Realized volatility - EMA slope - ADX -
Price efficiency - Volume percentile - Delta volatility

เมื่อมี L2 เพิ่ม: - Spread - Depth - Order Book Imbalance - Liquidity
depletion

## 16. Strategy A --- Absorption Reversal

``` text
Important Location
       ↓
Extreme Sell
       ↓
Low Price Impact
       ↓
CVD Divergence
       ↓
Sell Flow Deceleration
       ↓
Structure Reclaim
       ↓
LONG
```

กลับด้านสำหรับ Short

## 17. Strategy B --- Aggression Continuation

ใช้ตอน Imbalance/Trend:

``` text
Trend Down
    ↓
Sell Delta Extreme
    ↓
Price Impact HIGH
    ↓
Price ↓ + CVD ↓
    ↓
Pullback
    ↓
Sell Aggression returns
    ↓
SHORT
```

ดังนั้น: - Extreme Sell + Low Impact → Reversal candidate - Extreme Sell +
High Impact → Continuation candidate

## 18. Strategy C --- Trapped Trader

เมื่อเพิ่ม OI:

``` text
Breakout
    ↓
Buy Delta ↑↑
    ↓
OI ↑
    ↓
Price ไปต่อไม่ได้
    ↓
CVD High / Price Failed High
    ↓
กลับใต้ Breakout
    ↓
Trapped Long
    ↓
SHORT
```

Short trapped กลับด้าน

## 19. Big Bubble Engine

Phase ถัดไปใช้ `aggTrades`

``` text
TradeNotional = Price × Quantity
```

แยก Aggressor ด้วย Buyer Maker

ไม่ใช้ fixed threshold แบบ NQ แต่ใช้ dynamic threshold:

``` text
TradeNotional >= rolling 95 / 97 / 99 / 99.5 percentile
```

Classify: - Large Buy - Large Sell - Mega Buy - Mega Sell

## 20. Don't Trade the Bubble

กฎสำคัญ:

``` text
Big Buy ≠ Long
Big Sell ≠ Short
```

ต้องวัด Price Response หลัง Big Trade: - 5 sec - 15 sec - 30 sec - 1 min -
5 min

เก็บ: - Forward Return - MFE - MAE - Price Impact - Delta continuation

## 21. Phase 1 Event Study

ก่อน Strategy Backtest ให้ทดสอบ Absorption โดยไม่เข้าเงินจริง

ทุก Event บันทึก: - Return +1m - Return +3m - Return +5m - Return +15m -
Return +30m - Return +60m - MFE - MAE

## 22. Control Group

**สามกลุ่ม ไม่ใช่สองกลุ่ม**

**Group A**

``` text
Extreme Sell + Absorption
```

**Group B** — control เดิม

``` text
Extreme Sell + No Absorption
```

**Group C** — placebo

``` text
สุ่มเก็บสัญญาณ ที่สัดส่วนเท่ากับ A พอดี
ทำซ้ำอย่างน้อย 20 seeds
```

เปรียบเทียบ: - Forward Return - Hit Rate - MFE - MAE

``` text
ผ่านเมื่อ   A > B   และ   A > p90 ของ C
```

### ทำไมต้องมี Group C

Group B เก็บสัญญาณไว้เกือบทั้งหมด ส่วน Group A เก็บไว้ไม่กี่ตัว **เมื่อ baseline
ติดลบ การเทียบ A กับ B จึงกลายเป็นการเทียบ "เทรดน้อย" กับ "เทรดมาก"
ไม่ใช่การเทียบ "มี absorption" กับ "ไม่มี"**

ทดสอบจริงบน BTCUSDT รายวัน 3,276 แท่ง: Group A เหลือ **3 ไม้จาก 221** (0.7%) ·
Group B เก็บไว้ **99%** · A ชนะ B ด้วยระยะ **54 R** · แต่ Group C แบบสุ่ม
**16 จาก 20 seeds ทำได้ดีเท่าหรือดีกว่า A** ⇒ ตัวกรองไม่มี edge เลย
แต่เกณฑ์สองกลุ่มให้ผ่าน

``` text
Group B ตอบ  "absorption ดีกว่าไม่มี absorption ไหม"
Group C ตอบ  "absorption ดีกว่าทิ้งไม้แบบสุ่มจำนวนเท่ากันไหม"

คำถามที่สอง คือคำถามที่แยก edge จริง
ออกจากการเทรดน้อยลง
```

ถ้า A ไม่ชนะ B → Absorption definition ไม่มี edge
**ถ้า A ไม่ชนะ C → Absorption definition ไม่มีข้อมูลอยู่ในนั้นเลย** ต่อให้ชนะ B ขาดแค่ไหน

### ใช้กับทุกตัวกรอง ไม่ใช่แค่ absorption

Location Score (§14), Regime gate (§15), BORA Score threshold (§32), Flow
Efficiency (§12) — ทุกตัวคือตัวกรองที่ลดจำนวนไม้ **ทุกตัวต้องผ่าน Group C**

## 23. Parameter Matrix

ทดสอบ:

  Parameter           Values
  ------------------- ---------------------------
  Delta Z             1.5 / 2 / 2.5 / 3
  Volume percentile   90 / 95 / 97 / 99
  Price Impact        0.2 / 0.3 / 0.5 ATR
  Forward Horizon     1 / 3 / 5 / 15 / 30 / 60m

อย่าเลือก parameter ที่กำไรสูงสุดเพียงจุดเดียว ต้องหา **stable region** เพื่อหลีกเลี่ยง
overfit

### พื้นขั้นต่ำของจำนวนไม้ — ใช้ก่อนอ่านผลใด ๆ

ยิ่ง threshold เข้ม ยิ่งเหลือไม้น้อย และถ้าไม่มีพื้นขั้นต่ำ **แขนที่เหลือ 2 ไม้
ก็ผ่าน §22 / §23 / §25 ได้**

``` text
ไม้ < 30           →  NO VERDICT
                      รายงานว่า "ตัวอย่างไม่พอ" เท่านั้น
                      ห้ามใช้เป็นหลักฐานสนับสนุน แม้ตัวเลขจะสวย

ไม้ >= 30          →  อ่านผลได้

duty cycle < 5%    →  ต้องรายงาน duty ติดกับตัวเลขทุกครั้ง
```

### stable region นิยามอย่างไร

**ห้ามนิยามจากค่าที่ดีที่สุด** และห้ามนิยามจาก "ชนะกี่ช่อง" เฉย ๆ —
**ยิ่ง threshold สูง ยิ่งเทรดน้อย ยิ่งดูเสถียร เพราะไม่มีอะไรให้แกว่ง**

``` text
stable region =
ช่องข้างเคียงที่ผ่านพื้น 30 ไม้
และผ่าน Group C
ตั้งแต่ 2 ใน 3 ขึ้นไป
```

ทดสอบจริงบน SOL+LINK: แขน `Delta_Z` ชนะ baseline **3 จาก 3 ค่า** แต่เหลือ
25 / 15 / 5 ไม้ตามลำดับ ⇒ ภายใต้เกณฑ์นี้ **ไม่มีค่าไหนอ่านได้เลย** และ
"เสถียรภาพ" นั้นเป็นภาพลวง

## 24. Walk-Forward

ห้าม optimize 2020--2026 พร้อมกัน

``` text
TRAIN      2020–2022
VALIDATE   2023
TEST       2024

TRAIN      2021–2023
VALIDATE   2024
TEST       2025

TRAIN      2022–2024
VALIDATE   2025
TEST       2026
```

ห้ามใช้ Test data เลือก parameter

## 25. Strategy Benchmark

สร้างอย่างน้อย 6 Models:

  Model   Features
  ------- -------------------------------------
  M0      Random/Baseline
  M1      Price Action
  M2      Price + Volume Profile
  M3      Price + CVD
  M4      CVD + Absorption
  M5      State + Location + Absorption + CVD

เป้าหมายคือพิสูจน์ว่า M5 เพิ่ม **Incremental Edge** เหนือ M1--M4 หรือไม่

## 26. Execution Logic

เมื่อ Phase 1 ผ่าน:

``` text
Sell Absorption
     ↓
CVD divergence
     ↓
Location valid
     ↓
Price reclaim micro structure
     ↓
LONG
```

SL:

``` text
Below Absorption Zone
```

Invalidation: \> ถ้าราคาทะลุ absorption zone และ flow ยัง aggressive ต่อ →
Thesis ผิด → Exit

## 27. Take Profit

ทดสอบ: - 1R - 1.5R - 2R - 3R - 4R

Market-based TP: - VWAP - POC - VAH / VAL - Previous High/Low - LVN

Scaling candidate:

``` text
TP1 → 30%
TP2 → 30%
Runner → 40%
```

ต้องให้ Backtest ตัดสินว่า scaling เพิ่ม expectancy จริงหรือไม่

## 28. Cost Model

Scalping ห้าม Backtest แบบ Fee = 0

ต้องมี: - Maker Fee - Taker Fee - Slippage - Spread - Funding - Latency
assumption

Stress test: - Normal cost - 1.5× cost - 2× cost

ถ้า Strategy ตายเมื่อ cost เพิ่มเล็กน้อย → Edge ไม่แข็งแรง

## 29. Risk Engine

``` text
RiskAmount = Equity × RiskPerTrade

PositionSize =
RiskAmount / StopDistance
```

ทดสอบ RiskPerTrade: - 0.25% - 0.5% - 0.75% - 1%

เพิ่ม: - Daily Loss Limit - Max Consecutive Loss - Max Drawdown Gate -
Volatility Position Scaling

## 30. Metrics

Dashboard ต้องมี: - Net P/L / Net Return - Win Rate - Profit Factor -
Expectancy - Average R - Average Win / Loss - Max Drawdown - Time Under
Water - Sharpe / Sortino - Trades / Trades per month - MFE / MAE

Breakdown: - Long PF / Short PF - Bull / Bear / Sideway / High Vol PF -
Asia / London / New York - Year-by-year 2021--2026

## 31. Monte Carlo

สุ่มลำดับ trades อย่างน้อย `1,000–10,000 simulations`

วัด: - Median Return - 95% DD - Worst DD - Probability of Loss -
Probability DD \>20% - Risk of Ruin

## 32. BORA Score

Candidate version:

  Component              Weight
  ------------------- ---------
  Liquidity State            15
  Regime                     10
  Location                   20
  Flow Intensity             10
  Absorption                 20
  CVD Divergence             10
  Flow Acceleration           5
  Structure Trigger          10
  **Total**             **100**

Initial classification: - `<60` → NO TRADE - `60–69` → WATCH - `70–79` →
SETUP - `80+` → ENTRY CANDIDATE

Threshold เหล่านี้เป็น research parameters ไม่ใช่ค่าที่พิสูจน์แล้ว

## 33. Meta Labeling

เมื่อ Rule Engine stable แล้วค่อยใช้ ML

ไม่ให้ ML เริ่มจาก `Predict BTC Up/Down`

ใช้:

``` text
Rule Engine
    ↓
LONG Candidate
    ↓
ML Meta Model
    ↓
Probability TP before SL
    ↓
TRADE / SKIP
```

## 34. ML Features

Candidate features: - Delta_Z - CVD slope / divergence - Absorption
percentile - Flow efficiency - Flow acceleration - ATR percentile -
Volume percentile - Distance VWAP / VAH / VAL / POC - Regime - OI
change - Funding - Liquidation - Big Trade Buy/Sell - Time of Day - Day
of Week

Models เริ่มจาก: 1. Logistic Regression 2. XGBoost / LightGBM

ไม่จำเป็นต้องเริ่ม Neural Network

## 35. Agent Architecture

``` text
Data Agent
      ↓
Quality Agent
      ↓
Market State Agent
      ↓
Location Agent
      ↓
Order Flow Agent
      ↓
Absorption Detector
      ↓
Strategy Engine
      ↓
Meta Model
      ↓
Risk Gate
      ↓
Execution Agent
      ↓
Journal
      ↓
Learning / Research
```

**LLM ไม่ควรมีสิทธิ์ override Risk Gate**

## 36. Example Signal

``` text
BTCUSDT
5m

Market State
BALANCE → REVERSAL

Location
VAL + Previous Low

Delta
-2.8 Z

Sell Volume
98.6 percentile

CVD
New Low

Price
Higher Low

Absorption
99.1 percentile

Flow
Decelerating

Structure
Reclaim confirmed

────────────────

BORA LONG
Score: 86/100

Entry
xxxxx

Invalidation
Below Absorption Zone

TP1
2R

TP2
POC

Reason
Extreme aggressive selling
failed to produce proportional
downward price movement.
```

## 37. Development Roadmap

### Phase 1 --- Research

`Data → Delta → CVD → Price Impact → Absorption → Event Study → Control Group`

### Phase 2 --- Strategy

`+ Regime → Location → Reclaim → SL/TP → Cost`

### Phase 3 --- True Order Flow

`+ aggTrades → Big Bubble → Flow Velocity → Acceleration`

### Phase 4 --- Derivatives Intelligence

`+ OI → Funding → Liquidation → Trapped Trader`

### Phase 5 --- Robustness

`Walk-forward → Monte Carlo → Parameter Stability → BTC vs ETH`

### Phase 6 --- AI

`Meta-label → Trade/Skip probability → Explainability`

### Phase 7 --- Paper Trading

`Live public feed → Signal → Simulated Execution → Journal`

Liveเงินจริงควรเกิดหลัง Paper Trading ยืนยันว่า live behavior ใกล้กับ backtest
เท่านั้น

## 38. Definition of Success

ไม่ตั้ง Win Rate 70% เป็นเป้าหมายหลัก

ระบบผ่านเมื่อ:

``` text
Positive Expectancy
        +
PF > 1 after cost
        +
Acceptable Max DD
        +
Stable Walk-forward
        +
Multiple market regimes
        +
Parameter Stability
        +
Monte Carlo survives
        +
Paper ≈ Backtest
        +
ชนะการถือเฉย ๆ ที่ความเสี่ยงเท่ากัน
วัดเป็นการกระจายตัว ไม่ใช่เส้นทางเดียว
```

### ข้อสุดท้ายวัดอย่างไร

แปดข้อแรกผ่านครบได้ พร้อมกับแพ้การซื้อแล้วถือเฉย ๆ — ข้อที่เก้าจึงเป็นข้อที่
ฆ่ากลยุทธ์ได้จริงที่สุด และถูกที่สุดด้วย

``` text
1  ปรับ risk/ไม้ ให้ maxDD ของกลยุทธ์
   เท่ากับ maxDD ของการถือเฉย ๆ
   บนหน้าต่างเดียวกัน
   คาลิเบรตครั้งเดียว แล้วตรึงไว้

2  paired block bootstrap
   สับลำดับวันเป็นบล็อก (เช่น 20 วัน)
   ใช้ลำดับบล็อกเดียวกันกับทั้งสองฝั่ง
   อย่างน้อย 500 เส้น

3  นับสัดส่วนเส้นที่กลยุทธ์ชนะ
   ด้านความมั่งคั่งปลายทาง

4  ผ่านเมื่อชนะ >= 60% ของเส้น
   ประกาศก่อนรัน ห้ามปรับหลังเห็นผล

5  ไม่คิดค่าธรรมเนียมให้การถือเฉย ๆ
   (ให้แต้มต่อฝั่งที่ไม่ทำอะไร)
```

**ทำไมต้องเป็นการกระจายตัว**: กลยุทธ์หนึ่งบนเส้นทางจริงให้ **+107%** เทียบ
buy & hold **+49%** ที่ DD เท่ากัน — ดูเหมือนชนะสองเท่า พอสับประวัติศาสตร์
500 ครั้ง **ชนะแค่ 57%** ต่ำกว่าเกณฑ์ 60% ที่ประกาศไว้ก่อน

``` text
การเทียบเส้นทางเดียว
ให้คำตอบผิดเครื่องหมายได้
ไม่ใช่แค่คลาดเคลื่อน
```

### ลำดับที่ควรถาม — ด่านที่ฆ่าได้ไวและถูกที่สุดอยู่ต้น

``` text
1  ประกาศเกณฑ์และตัวเลขที่ถือว่าผ่าน ก่อนรัน
2  พื้นขั้นต่ำจำนวนไม้ (§23)
3  Group C placebo (§22)          ← ตก = หยุด
4  Group B control (§22)
5  Incremental edge เหนือ M0–M4 (§25)
6  Walk-forward (§24)
7  Cost stress 1.5x / 2x (§28)
8  Monte Carlo (§31)
9  ชนะการถือเฉย ๆ เป็นการกระจายตัว  ← ตก = ไม่คุ้มทำ
```

ข้อ 3 และข้อ 9 คือสองข้อที่ฆ่ากลยุทธ์ซึ่งรอดข้ออื่นมาแล้ว

Strategy ที่มี `Win Rate 48% + Avg Win 2R + Avg Loss 1R` อาจดีกว่า Strategy
Win Rate 75% ที่ Avg Win เล็กและ Tail Loss ใหญ่

## Core Thesis

> **เราไม่ได้เทรดว่าใครซื้อหรือขายเยอะ แต่เทรด "ความสามารถหรือความล้มเหลวของ
> Aggressive Flow ในการขยับราคา" ณ Location และ Market State ที่เหมาะสม**

BORA จึงควรถูกพัฒนาเป็น **microstructure research framework**
ที่สามารถพิสูจน์หรือหักล้างแต่ละ edge ด้วย Backtest ก่อนนำไปใช้กับ Paper Trading และ
AI Execution
