# E41 — Fee/DEX-vol relative-strength rotation (Osmo S2) (ประกาศก่อนรัน)

> **สถานะ: RUN แล้ว — ❌ FAIL (G2, G5a ตก; G1/G3/G4 ผ่าน)** (2026-08-12)
> ผลเต็ม `docs/VALIDATION_LOG.md` § E41 · ผลดิบ `docs/dex-rotation-e41.json`
> R_dex **ชนะ** R_price (mean robust −0.84 vs −0.98, ชนะ 3/5 หน้าต่าง) และชนะ R_eq
> แต่ **mean robust ติดลบ** และ held-out เวลาก็ติดลบ · BNB ไม่ถูกแตะ
> · เนื้อหาด้านล่างคือฉบับที่ประกาศก่อนรัน **ไม่ถูกแก้หลังเห็นผลแม้แต่บรรทัดเดียว**
>
> _(สถานะเดิมตอนประกาศ: DECLARED — ยังไม่รัน, 2026-08-12)_
> ไฟล์นี้เขียนเสร็จ **ก่อน** เขียนโค้ดทดลองแม้แต่บรรทัดเดียว และห้ามแก้หลังเห็นผล
>
> **หมายเลข**: รันครั้งแรกเขียนเป็น E40 โดยชนกับ E40 sizing (2026-08-11) จึงย้ายมา
> E41 โดย**ไม่แก้เกณฑ์หรือผล** · E40 ยังเป็น trend-sizing ตามเดิม

## 0. คำถามและขอบเขต

> **การเติบโตของ DEX volume ราย chain ใน 7 วัน คาดการณ์ผลตอบแทนสัมพัทธ์
> ของสินทรัพย์หลักของ chain นั้น ได้ดีกว่าการหมุนตามผลตอบแทนราคา 7 วัน
> หรือการถือเท่า ๆ กัน หรือไม่**

**กลไก**: กิจกรรมจริง (volume ที่แลกบน DEX) นำความสนใจและทุน · ราคาของ ETH/SOL/BNB
ยังไม่สะท้อนครบในวันที่ volume พุ่ง → relative-strength จาก activity มี residual
เหนือ price momentum

**ทำไมไม่ใช่ E33 screen**
E33 คัดเหรียญจาก conditional gap ของ SMA-200 แล้วล้ม · E41 ไม่มี screen ประวัติ
ผลตอบแทน — ใช้เฉพาะ footprint กิจกรรมจาก DefiLlama ที่คนละกลไก

## 1. กับดักที่ต้องกันก่อน

| กับดัก | วิธีกัน |
|---|---|
| **แค่ momentum ราคาในคราบ volume** | แขน control **R_price** รายงานเสมอ · ผ่านได้เฉพาะเมื่อ R_dex ชนะ R_price |
| **lookahead ของ volume รายวัน** | ที่วัน `t` ใช้ `vol[t]` ได้เมื่อปิดวัน · เข้าที่ `close[t]` |
| **จูนหน้าต่าง 7 วัน** | ล็อก 7 · รีบาลานซ์ทุก 7 แท่ง · ห้ามลอง 3/14/30 หลังเห็นผล |
| **survivorship** | จักรวาล primary = **ETH + SOL เท่านั้น** |
| **held-out ปน** | 252 แท่งสุดท้าย = held-out เวลา · **BNB/BSC** = held-out สินทรัพย์ |
| **หลายการวัด** | primary ข้อเดียว: R_dex vs R_price |

## 2. ข้อมูล

| รายการ | ค่า |
|---|---|
| ราคา | `data/universe/spot_1d.json` — ETH, SOL (primary) · BNB (held-out) · BTC (benchmark) |
| DEX vol | DefiLlama `GET /overview/dexs/{Ethereum,Solana,BSC}` → `totalDataChart` |
| Snapshot | `data/dex_vol/` |
| Held-out เวลา | **252 แท่งสุดท้าย** ห้ามใช้ตัดสิน G1–G4 |
| Held-out สินทรัพย์ | BNB + BSC — ห้ามแตะจนกว่า G1–G4 ผ่าน |

## 3. กติกา (ล็อก)

ที่วันรีบาลานซ์ `t` (ทุก 7 แท่ง หลัง warmup 60):

- `g_c(t) = vol_c[t] / vol_c[t − 7] − 1`
  - ETH ← Ethereum · SOL ← Solana · (BNB ← BSC เฉพาะ held-out)
- **R_dex**: ถือ 100% สินทรัพย์ที่ `g_c` สูงสุด
- **R_price**: เหมือนกันแต่ใช้ผลตอบแทนราคา 7 วัน
- **R_eq**: ETH+SOL อย่างละ 50%
- **R_btc**: ถือ BTC
- **R_rand**: สุ่ม (seed = 0)

ต้นทุน **0.15%/ขา** · long-only · ไม่มี leverage

**Primary:** บน OOS 252 ไม่ทับกัน (ไม่รวม held-out เวลา):
mean(robust R_dex) > mean(robust R_price) และชนะ >50% ของหน้าต่าง

## 4. เกณฑ์ตัดสิน (ไม่ลด)

| id | เกณฑ์ |
|---|---|
| G1 | Primary ข้างบน |
| G2 | mean robust R_dex > 0 |
| G3 | mean robust R_dex > R_eq |
| G4 | รีบาลานซ์ ≥ 30 |
| G5a | held-out เวลา: R_dex robust > R_price และ > 0 |
| G5b | จักรวาล 3 ตัวรวม BNB แล้วยังชนะ R_price ที่ mean robust |

**ผ่าน = G1–G4 + G5a + G5b** · ไม่ promote ไปเทรดจริง

## 5. ตารางการตัดสินใจ / สิ่งที่ไม่ทำ

ดูฉบับประกาศเดิม: ห้ามจูน 7 วัน · ห้ามแตะ held-out ก่อน G1–G4 · ไม่มีคำสั่งจริง
