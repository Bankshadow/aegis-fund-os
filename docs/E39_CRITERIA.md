# E39 — Crowded-long liquidation fade (Osmo S1) บน BTC (ประกาศก่อนรัน)

> **สถานะ: RUN แล้ว — ❌ FAIL (G1–G4 ตก; G5 ไม่ประเมิน)** (2026-08-12)
> ผลเต็ม `docs/VALIDATION_LOG.md` § E39 · ผลดิบ `docs/crowding-fade-e39.json`
> **S_full n=0** — ระบอบ crowded (L/S∧funding∧OI) **ไม่เคยทับ** impulse 0.5×ATR
> ในหน้าต่างสาธารณะ ~30 วัน · ตาม §6 ห้ามผ่อน threshold · เนื้อหาด้านล่างคือฉบับที่
> ประกาศก่อนรัน **ไม่ถูกแก้หลังเห็นผลแม้แต่บรรทัดเดียว**
>
> _(สถานะเดิมตอนประกาศ: DECLARED — ยังไม่รัน, 2026-08-12)_
> ไฟล์นี้เขียนเสร็จ **ก่อน** เขียนโค้ดทดลองแม้แต่บรรทัดเดียว และห้ามแก้หลังเห็นผล
> (แก้ได้เฉพาะกรณี spec ขัดกับตัวเอง และต้องแก้ *ก่อน* รัน พร้อมบันทึกเหตุผล — บทเรียน E29)
>
> ที่มา: workflow จาก [@Flowslikeosmo top-10 tools](https://x.com/Flowslikeosmo/status/2087162227677962566)
> · candidate **S1** ใน canvas osmo-toolbelt-strategies · **ไม่ใช่การรีรัน E17**

## 0. คำถามและขอบเขต

> เมื่อ **L/S สูง + funding สูง + OI ขยาย พร้อมกัน** แล้วราคาพุ่งเป็น impulse
> การ fade (สวนทิศขึ้น) ให้ผลดีกว่า funding อย่างเดียว / L/S อย่างเดียว /
> impulse อย่างเดียว / สุ่ม หรือไม่

**ทำไมไม่ใช่ E17**

| | E17 | E39 |
|---|---|---|
| สัญญาณ | funding percentile เดี่ยว | **สามปัจจัยร่วม** + impulse trigger |
| บทบาท | directional bias ใน grid | measurement ของ liquidation-fuel regime |
| ผลก่อนหน้า | FAIL engaged 33% | — |

**ข้อจำกัดข้อมูล (ประกาศก่อนรัน — ไม่ใช่ข้ออ้างหลังผลแย่)**

Binance public `globalLongShortAccountRatio` และ `openInterestHist`
เก็บได้แค่ **~30 วันล่าสุด** (เอกสาร API: "Only the data of the latest 30 days")
จึง**ห้าม**อ้าง multi-year walk-forward แบบ E30 · การทดลองนี้เป็น
**measurement บนแผง 1h ที่ซ้อนทับได้จริง** · ถ้าผ่าน ขั้นถัดไปต้องมีแหล่ง
ประวัติยาว (เช่น Coinglass paid) ก่อน promote แม้แต่ paper

## 1. กับดักที่ต้องกันก่อน

| กับดัก | วิธีกัน |
|---|---|
| **รีรัน E17 ในคราบใหม่** | แขน control **funding-only** รายงานเสมอ · ผ่านได้เฉพาะเมื่อ full crowded ชนะ funding-only |
| **จูน threshold ตาม 30 วันนี้** | ล็อกค่าด้านล่างจาก snapshot/ตำรา ก่อนรัน |
| **lookahead** | จัดชั้นที่แท่ง `i` ใช้ L/S, OI, funding, ATR จากข้อมูล ≤ i เท่านั้น · forward เริ่มจาก close[i] |
| **n เล็ก** | ประกาศ G4: n≥20 ที่ primary · ถ้าน้อยกว่า = ไม่พอเป็นหลักฐาน ห้ามผ่อน threshold |
| **หลายการวัด** | primary ข้อเดียว · ที่เหลือ robustness |
| **สับสนกับกลยุทธ์เทรดจริง** | ชั้นหลัก = measurement ของ fade score · ชั้น strategy (long↔cash) รายงานเป็น secondary เท่านั้น |

## 2. ข้อมูล

| รายการ | ค่า |
|---|---|
| L/S | Binance `globalLongShortAccountRatio` BTCUSDT **1h**, เต็มช่วงที่ API ให้ |
| OI | Binance `openInterestHist` BTCUSDT **1h** (sumOpenInterestValue) |
| Funding | Binance `fundingRate` BTCUSDT ในช่วงเดียวกัน (8h → forward-fill ลงแท่ง 1h) |
| ราคา | Binance futures klines BTCUSDT **1h** ซ้อนทับช่วงเดียวกัน |
| Held-out | ETHUSDT, SOLUSDT แผงเดียวกัน — **ห้ามแตะจนกว่า primary บน BTC จะผ่าน G1+G4** |
| Snapshot ดิบ | บันทึกลง `data/crowding/` ตอนรัน (reproduce ได้) |

## 3. นิยาม (ล็อก ห้ามจูน)

ที่แท่ง 1h ดัชนี `i` (ต้องมีประวัติ ATR ≥ 14 และ OI ย้อน 24 แท่ง):

**Crowded** เมื่อครบทั้งสามข้อ:
1. `longShortRatio[i] ≥ 1.50`
2. `funding_ffill[i] ≥ 0.0001` (= 0.01% ต่อรอบ — ระดับที่เห็นบน snapshot)
3. `oi_value[i] > oi_value[i − 24]` (OI ดอลลาร์สูงกว่า 24 ชม.ก่อน)

**Impulse_up** เมื่อ:
- `close[i] > close[i − 1]` และ
- `(close[i] − close[i − 1]) ≥ 0.5 × ATR(14)[i]`  
  ATR = SMA ของ TR 14 แท่ง**ก่อนหน้า** (ไม่รวม i) — ตรงกับ E36 volume ATR style

**สัญญาณ full (S_full)** = Crowded ∧ Impulse_up  
**Control funding-only (S_fund)** = (funding ≥ 0.0001) ∧ Impulse_up  
**Control L/S-only (S_ls)** = (L/S ≥ 1.50) ∧ Impulse_up  
**Control OI-only (S_oi)** = (OI ขึ้น 24h) ∧ Impulse_up  
**Control impulse-only (S_imp)** = Impulse_up  
**Control random (S_rand)** = สุ่มแท่งจำนวนเท่า S_full (seed 0, ห้ามใช้ผลเลือก seed)

**Fade score** ที่ horizon h ∈ {4, 12, 24} ชม.:
`fade_h = −(close[i+h]/close[i] − 1)`  
(บวก = การ short/fade ได้กำไร)

**Primary test (ข้อเดียว):**
> ที่ **h=12**: mean(fade | S_full) ชนะ mean(fade | S_fund)  
> bootstrap 10,000 ครั้ง สุ่มป้ายบนพูลสองกลุ่ม → **percentile ≥ 95%**

## 4. ชั้น secondary (รายงานเสมอ ไม่ใช่เกณฑ์ผ่านหลัก)

Strategy long↔cash บนช่วง 30 วันเดียวกัน:
- เริ่มถือ long 1x spot-equiv ที่ close แรกที่ใช้ได้
- เมื่อ S_full → ออกเป็นเงินสด 12 แท่ง แล้วกลับเข้า long
- ต้นทุน 0.15%/ขา (เหมือน E30 spot)
- เทียบ buy&hold และ funding-only rule เดียวกัน
- รายงาน return, maxDD, robust — **ห้ามใช้ชั้นนี้ตัดสินผ่าน/ตกแทน G1**

## 5. เกณฑ์ตัดสิน (ไม่ลด)

| id | เกณฑ์ | ผ่านเมื่อ |
|---|---|---|
| G1 | Primary: S_full fade ชนะ S_fund ที่ h=12 | **percentile ≥ 95%** |
| G2 | S_full fade mean > 0 ที่ h=12 | บวกจริง |
| G3 | S_full ชนะ S_imp และ S_rand ที่ h=12 (mean) | ทั้งคู่ |
| G4 | n(S_full) ≥ 20 และ n(S_fund) ≥ 20 | ทั้งคู่ |
| G5 | held-out ETH **และ** SOL ทิศ primary เดียวกัน | ทั้งคู่ |

**"ผ่าน" = G1–G5 ครบ** · ผ่านบางข้อ = ⚖️ บันทึกแต่ไม่ promote  
**ไม่ว่าผลออกทางไหน จะไม่ promote ไปเทรดจริง** · แม้ผ่านก็ยังติดข้อจำกัดประวัติ 30 วัน

## 6. ตารางการตัดสินใจ (เขียนก่อนเห็นผล)

| ผล | อ่านว่า | ทำอะไรต่อ |
|---|---|---|
| G1–G5 ผ่าน | crowding รวมมีสาระเหนือ funding บนหน้าต่างนี้ | บันทึก · **ยังไม่ promote** · ต้องหาประวัติยาวก่อน E40 |
| G1 ผ่าน แต่ G4 ตก | ทิศทางโอเคแต่ n ไม่พอ | ⚖️ ไม่ใช่หลักฐาน |
| G1 ตก แต่ G2 ผ่าน | fade ได้แต่ไม่ชนะ funding-only | FAIL กลไกรวม — **E17 ถูกยืนยันว่าพอแล้วสำหรับ funding** |
| G1 และ G2 ตก | crowding+impulse ไม่ให้ fade edge บนชุดนี้ | FAIL · **ปิด S1 บนแผงสาธารณะ 30 วัน** |
| n < 20 | ไม่พอ | รายงาน · **ห้ามผ่อน L/S หรือ funding threshold เพื่อเพิ่ม n** |

## 7. สิ่งที่การทดลองนี้จะไม่ทำ

- ไม่จูน 1.50 / 0.0001 / 0.5×ATR / horizon หลังเห็นผล
- ไม่ดึง Coinglass paid หรือแหล่งอื่นที่ไม่ได้ประกาศใน §2
- ไม่แตะ held-out ก่อน G1+G4 บน BTC
- ไม่มีคำสั่งจริง ไม่มี leverage ในชั้น measurement
- **ไม่ตอบว่า BTC จะไปทางไหนวันนี้** — วัดคุณสมบัติของระบอบ crowding
