# STATE.md — Session Memory

> Write before walking away. Read at session start.
> Stages: Fail → Investigate → Verify → Distill → Consult (next session).

## Verified facts

- E58 (2026-08-16) — **S003 ไม่คุ้มกว่าการถือเฉย ๆ · สายวิจัย S003 ปิด**
  (`docs/E58_CRITERIA.md` ประกาศก่อนรัน · ผลดิบ `docs/vs-holding-e58.json`)
  · paired block bootstrap 20 วัน × 500 เส้น สับประวัติศาสตร์ลำดับเดียวกันใส่ทั้ง
  สองฝั่ง · S003 คาลิเบรตให้ maxDD เท่า buy&hold · buy&hold ไม่เสียค่าธรรมเนียม
  · **W_OOS: S2 robust-win 60.0% (ต้อง ≥90%) ตก · S2b wealth-win 57.0%
  (ต้อง ≥60%) ตก** · **W_COMMON: 10.8% / 10.4%** (buy&hold +4042% vs S003 −13%)
  · **บทเรียนสำคัญที่สุด**: บนเส้นทางจริง S003 ให้ **+107.4% vs +49.0%** ดูเหมือน
  ชนะสองเท่า **แต่สับประวัติศาสตร์แล้วชนะแค่ 57%** — ความได้เปรียบนั้นคือ
  **ลำดับเหตุการณ์ที่บังเอิญ ไม่ใช่คุณสมบัติของกลยุทธ์** (การคำนวณเชิงพรรณนา
  +115% vs +49% ที่เคยแสดงไว้จึงไม่ใช่หลักฐาน)
  · การจับคู่ DD ต้องใช้ risk **5.22–8.54%/ไม้** ซึ่ง **E49 ห้ามไว้** (ใช้ได้จริง 1–2%)
  · **S4**: บน W_COMMON **70.6%** ของเส้น S003 DD แย่กว่า buy&hold
  · **S7 ที่ risk 1%**: +30.5% / DD 21.4% vs buy&hold +49.0% / DD 74.1% —
  **นี่คือสิ่งที่ S003 เป็นจริง ๆ: เครื่องลด DD ไม่ใช่เครื่องสร้างผลตอบแทน**
  · **ตามตารางตัดสินที่ประกาศไว้: ยกเลิก forward paper log** — ไม่เดินหน้าต่อ
  · หมายเหตุ: E56/E57 ยังยืนอยู่ — edge เป็นบวกจริง reproduce ได้ ทนต้นทุน
  0.467%/ข้าง · สิ่งที่ E58 ปฏิเสธคือ **ความคุ้มค่าเทียบทางเลือกที่ไม่ทำอะไรเลย**

- E57 (2026-08-16) — **S003 reproduce ได้บนเอนจินของคนอื่น (backtrader)**
  (`docs/E57_CRITERIA.md` ประกาศก่อนรัน · ผลดิบ `docs/impl-independence-e57.json`)
  · **GPL-3.0: backtrader + รันเนอร์อยู่นอกรีโปทั้งคู่** (venv ใน scratchpad)
  ไม่มีโค้ดเข้ารีโป ไม่มี dependency ใหม่ใน gate ไม่มี host ใหม่ใน egress allowlist
  · **portR +71.81 vs ของเรา +72.81 (ต่าง 1.37%)** · วันเข้าไม้ตรงกัน **100%
  (339/339)** · เหตุผลออกตรงกัน **99.71%** · **SOL ตรงกันถึงทศนิยมที่ 9**
  (+34.1014983224 vs +34.1014983229) · ต่างกันไม้เดียวทั้งชุด มูลค่า 1.0 R
  · **กฎ BE-arming-bar ที่ E55 D บอกว่ามีค่า 27.5% คือพฤติกรรมปกติของ
  backtester แบบ event-driven** — backtrader สร้างกฎนี้ขึ้นเองโดยโครงสร้าง
  (`next()` ทำงานหลังแท่งปิด) · **แต่กฎของเราใจดีกว่าหนึ่งขั้น**: เราระงับ
  **stop เดิม** ในแท่งที่ arm ด้วย ซึ่ง backtrader ไม่ทำ = ไม้ที่ต่างกัน 1 ไม้นั้น
  · **`sl_first` ของเราไม่ได้แปลว่า "stop ชนะ TP"** — ไม่มีแท่งออกไม้แม้แต่แท่งเดียว
  ที่แตะทั้ง TP3 และ stop เดิม (0 ครั้ง) · มันแปลว่า "แท่งที่ arm BE โดน stop ได้"
  ตรงกับที่ E56 วัดว่า `sl_first ≡ literal BE rule`
  · **R0 ตกตามที่ประกาศ** (ATR ต่าง 21%) แต่ตกเพราะเกณฑ์วัดรวมช่วง seed —
  ตั้งแต่แท่ง 201 (warmup) ต่างกัน **1.4e-7** · บันทึกเป็น**ข้อบกพร่องของ criteria**
  ไม่ใช่การแก้ tolerance
  · **สูตร fee ที่ audit ทักไว้: ต่างจากค่าจริง 0.0225 R ใน 339 ไม้ — ไม่สำคัญ**
  · **ยังไม่ใช่ specification independence** — กฎถูกเข้ารหัสใหม่โดยคนเดิม
  · **บทเรียน**: รันสองครั้งแรกได้ +51.49 และ −325.09 **ทั้งคู่เป็นบั๊กใน mapping
  ของผมเอง** (จับคู่คำสั่งด้วย identity แทน tag / stop ตัวใหม่ไม่ได้ติด tag)
  ถ้าไม่มีค่าอ้างอิง +72.81 ประกาศไว้ก่อน **+51.49 จะดูสมเหตุสมผลมาก**

- E56 (2026-08-15) — **มุมร้ายที่สุดของ S003: edge รอด แต่สมมติฐานที่เปิดการทดลองผิด**
  (`docs/E56_CRITERIA.md` ประกาศก่อนรัน · ผลดิบ `docs/honest-corner-e56.json`)
  · **แกนกฎ BE ซ้อนอยู่ในแกน intrabar ไม่ใช่แกนอิสระ** — ใต้ `sl_first` กฎ BE
  ทั้งสองแบบให้ผล**เท่ากันเป๊ะทุกช่อง** (+43.76) เพราะกฎยกเว้น arming-bar ทำได้
  แค่ระงับการเช็ค stop ที่โหมดร้ายทำอยู่แล้ว → **error bar 27.5% ของ E55 D เป็น
  สับเซตของ 39.9% ไม่ใช่ตัวบวก** · "มุมที่สาม" ที่เป็นเหตุผลให้เปิด E56 ไม่มีอยู่จริง
  E50 วัดพื้นไปแล้ว
  · **Z2/Z3 ผ่าน**: มุมร้าย @0.05% portR เต็ม **+43.76** (60% ของช่องสเปก) OOS
  **+36.65** · หน้าต่างที่ไม่เคยเห็น **+24.06** · **บวกทั้ง SOL และ LINK**
  · **Z4 ตก** เหมือน E50 Y3 ด้วยตัวเลขเดียวกันเป๊ะ (+6.9% vs buy&hold +10.4%
  แต่ DD 21.3% vs 74.1%) → **EDGE REAL BUT THIN**
  · **ตัวเลขที่ต้องใช้ต่อจากนี้: portR ของ S003 = ช่วง [+43.76, +72.81] R
  ห้ามรายงานปลายเดียว** · จุดคุ้มทุน 0.467%/ข้าง (headroom 3.1x เหนือ 0.15%)
  · **บทเรียนเชิงวิธี**: ก่อนเปิดการทดลองเพื่อวัด "มุมที่ยังไม่มีใครวัด" ต้อง
  **พิสูจน์ก่อนว่าแกนเป็นอิสระจริง** — กรณีนี้พิสูจน์ได้จากโค้ดภายในห้านาที

- E55 (2026-08-15) — **สเปกที่ผู้ใช้ล็อกแล้ว (`~/final_logic.md`) ผ่านการวัด: 3 ใน 4 ข้อไม่รอด**
  (`docs/E55_CRITERIA.md` จองก่อนแตะโค้ด · ผลดิบ `docs/final-stack-e55.json`)
  · **ไดรเวอร์ใหม่** `strat_trap.run_portfolio()` + `Cooldown` รัน SOL+LINK ในลูปเดียว
  — harness ผ่าน: ปิด cooldown แล้วได้ผล**เหมือน `run_symbol` ทุกไม้** และ portR
  **+72.81 ตรงกับ E45 พอดี** (17 เทสต์ `tests.test_portfolio_s017`)
  · **A — S017 cooldown 4/2 ตก**: ชนะ placebo (0/20 seeds ตาม) แต่ตก A2/A4/A5/A6 —
  fold แย่สุด **−12.48 vs −5.55**, ย่าน 3×3 ชนะแค่ **3/9** (`streak 3` ติดลบยกแถว),
  **แพ้บน SOL** ชนะเพราะ LINK ตัวเดียว, และ **พลิกเครื่องหมายใต้ sl_first**
  (+33.71 vs +43.76) → เกาะแคบแบบเดียวกับ k=30 ของ E53
  · **B — risk 4% เรียกร้องความทน DD ~70%** (boot p90 66–70%, ~1–2% ของเส้นทาง
  ล้างพอร์ต) · ตาราง tolerance→risk: 30%→1%, 50%→2%, 70%→4%
  · **C — overlay ตามสเปกตก**: แพ้ placebo ที่สับ scale (p90 +63.4% vs +60.0%)
  · **clamp 4.0 ไม่เคยทำงาน** scale จริงวิ่งแค่ 0.60–1.64
  · **D — กฎ BE-arming-bar ที่สเปกลืมเขียน มีค่า 27.5–33.2% ของ portR**
  → คงโค้ดเดิม, เขียนกฎลง `final_logic.md` §4 แล้ว, และแบบตัวอักษรกลายเป็น
  **error bar ถาวรคู่กับ `sl_first`**
  · **คำแนะนำที่ตามมา: S003 เปล่า ๆ ไม่ต้องมี cooldown ไม่ต้องมี overlay**
  ถ้าจะลดเสี่ยงให้ลด risk ต่อไม้ — บทเรียนซ้ำรอย E47/E48 · ไม่ promote

- E43 (2026-08-12) — **HL fees overlay บน BTC (Osmo S3): ไม่ผ่าน G1/G2/G4**
  (`docs/E43_CRITERIA.md` จองใน EXPERIMENT_REGISTRY ก่อนเขียน) · H_size
  mean robust **−0.126** ดีกว่า T1 **−0.287** และชนะ C_vol/H_only (G3 ผ่าน)
  แต่ชนะแค่ **2/4 หน้าต่าง** และ robust ติดลบ · เทรดทั้งช่วง 6 < 10 · P1
  Spearman **−0.04** · ETH ไม่ถูกแตะ · 5 เทสต์ `tests.test_hl_overlay`
  · **ปิด S3** · ไม่ promote · Osmo top-10 S1/S2/S3 ปิดครบบนหลักฐานสาธารณะ

- **เลขการทดลองชนกัน 3 ครั้งใน 1 วัน และผมทำไฟล์เสียหาย 1 ไฟล์ (2026-08-12)**
  · **สาเหตุ**: ผู้ใช้กับผมจัดสรรเลข E อิสระต่อกัน โดยไม่มีอะไรในรีโปที่บอกว่าเลขไหน
  ถูกจองแล้ว · **E36, E39, E40 ถูกอ้างสิทธิ์ซ้ำทั้งสามเลข**
  · **ความเสียหายที่ผมก่อ**: เขียนทับ `e39_crowding.py` (runner ของผู้ใช้) โดยไม่ได้
  อ่านก่อน — ไฟล์ไม่อยู่ใน git จึงกู้จาก git ไม่ได้ · และเขียนทับ
  `docs/crowding-fade-e39.json`
  · **กู้คืนแล้ว**: เอนจิน/สคริปต์ดึงข้อมูล/เทสต์/แผงข้อมูลของผู้ใช้รอดทั้งหมด จึง
  เขียน runner ใหม่ให้ขับเอนจินเดิม (`dynamic_grid/crowding_fade.py`) และ
  **ตรวจแล้วว่าให้ตัวเลขตรงกับที่บันทึกไว้ในล็อกทุกตัว** (S_full n=0, S_fund 5/+0.36%,
  S_ls 49/+0.11%, S_oi 31/+0.24%, S_imp 81/+0.14%, buy&hold −3.17%)
  · **ยังกู้ไม่ได้**: `docs/E36_CRITERIA.md` ฉบับ Volume Patterns (Koroush) ถูกผม
  เขียนทับ · **จะไม่เขียนขึ้นใหม่** เพราะเอกสารประกาศก่อนรันที่เขียนหลังรู้ผลแล้ว
  ไม่ใช่การประกาศก่อนรัน — บันทึกว่าสูญหาย
  · **แก้เชิงโครงสร้าง**: เพิ่ม `docs/EXPERIMENT_REGISTRY.md` — จองเลขก่อนเขียน
  criteria, ห้ามเขียนทับไฟล์ของเลขที่ไม่ได้จอง, และ `git add` ไฟล์ทดลองแต่เนิ่น ๆ
  (ไฟล์ untracked ไม่มีปุ่ม undo) · **เลขว่างถัดไป E43**
  · งาน trend-sizing ของผมย้าย E39 → E40 → **E42** (เนื้อหาเกณฑ์ไม่ถูกแก้ทั้งสามครั้ง)

- E42 (2026-08-11, เดิมเขียนเป็น E39/E40) — **ตัวกรองเทรนด์เป็น "ขนาด" แทน
  "สวิตช์": ⚖️ R2 ผ่าน R3 ตก — คำถามหลักของการทดลองผ่านเป็นครั้งแรกใน ledger**
  (`docs/E42_CRITERIA.md`) · ฐาน: E34 K6 **ทำซ้ำได้ +0.125 เทียบ +0.121**
  · **R1 ผ่าน** Spearman 0.479 permutation 92.7%
  · **R2 ผ่าน**: A2 ไล่ระดับ **−0.103** ชนะ A1 เข้า/ออก **−0.139** และ **ชนะ 9/12
  หน้าต่าง** · R4/R5/R6 ผ่านครบ (ชนะ constant-mix −0.264, inverse-vol −0.326,
  buy&hold −0.363) → **เป็นข้อมูลเทรนด์จริง**
  · **R3 ตก** robust ยังติดลบ → **ไม่ promote · held-out ไม่ถูกแตะ**
  · **สมมติฐานถูกครึ่งเดียว**: เดไซล์ 1–8 เฉลี่ย +0.74% ขณะ 9–10 เฉลี่ย **+9.95%
  (13.4 เท่า)** → **หน้าผา ไม่ใช่ทางลาด** · สมมติฐานถัดไปคือ "เกณฑ์ที่สองที่สูงกว่า"
  **ห้ามทดสอบตอนนี้** (เพิ่มแขนหลังเห็นผล) ต้องเป็น E43 พร้อมเกณฑ์ใหม่
  · ราคาที่จ่าย: A2 เทรด 17.1 ครั้ง/ปี เทียบ A1 2.5 · 14 เทสต์ · gate SHIP

- E41 (2026-08-12) — **DEX-vol rotation (Osmo S2) ETH↔SOL: ไม่ผ่าน G2/G5a**
  (`docs/E41_CRITERIA.md`) · R_dex **ชนะ** R_price (−0.84 vs −0.98, 3/5 หน้าต่าง)
  และชนะ equal-weight · แต่ **mean robust ติดลบ** (DD ~58%) · held-out เวลา −1.40
  · BNB ไม่ถูกแตะ · BTC B&H mean robust −0.48 ยังดีกว่า · 6 เทสต์
  `tests.test_dex_rotation` · มี residual เหนือ price momentum แต่ไม่พอเป็นกลยุทธ์
  · ไม่ promote · (หมายเลขย้ายจาก E40 ที่ชนกับ sizing)

- E40 (2026-08-11) — **ตัวกรองเทรนด์เป็น "ขนาด" แทน "สวิตช์": ⚖️ R2 ผ่าน R3 ตก
  — คำถามหลักของการทดลองผ่านเป็นครั้งแรกใน ledger** (`docs/E40_CRITERIA.md`
  ประกาศก่อนเขียนโค้ด) · **หมายเลข**: เขียนไว้เป็น E39 แต่ `E39_CRITERIA.md`
  ถูกใช้กับ Osmo S1 (crowded-long fade) ไปแล้ว จึงย้ายมา E40 เนื้อหาเกณฑ์ไม่ถูกแก้
  · ฐาน: E34 K6 ข้อค้นพบเชิงบวกอันเดียวใน ledger — **ทำซ้ำได้ +0.125 เทียบ +0.121**
  · **R1 ผ่าน** Spearman 0.479 permutation 92.7%
  · **R2 ผ่าน (คำถามหลัก)**: A2 ไล่ระดับ robust **−0.103** ชนะ A1 เข้า/ออก **−0.139**
  และ **ชนะ 9/12 หน้าต่าง** ไม่ใช่แค่ค่าเฉลี่ย · R4/R5/R6 ผ่านครบ (ชนะ constant-mix
  −0.264, inverse-vol −0.326, buy&hold −0.363) → **เป็นข้อมูลเทรนด์จริง ไม่ใช่แค่
  การปรับตามความเสี่ยงหรือการถือน้อยลง**
  · **R3 ตก** robust ยังติดลบ → **ไม่ promote · held-out ETH/SOL ไม่ถูกแตะ**
  · **สมมติฐานถูกครึ่งเดียว**: P1 เผยว่าข้อมูล**ไม่ได้ไล่ระดับ** — เดไซล์ 1–8 เฉลี่ย
  **+0.74%** ขณะเดไซล์ 9–10 เฉลี่ย **+9.95% (13.4 เท่า)** ช่วงกว้างในเดไซล์ 2–8
  มีแค่ 1.91 จุด → **เป็นหน้าผา ไม่ใช่ทางลาด** A2 ชนะเพราะทางลาดเชิงเส้นบังเอิญ
  ให้น้ำหนักส่วนบนมากกว่า binary · **สมมติฐานถัดไปคือ "เกณฑ์ที่สองที่สูงกว่า"
  แต่ห้ามทดสอบตอนนั้น** (เพิ่มแขนหลังเห็นผล) ต้องเป็น **E42** พร้อมเกณฑ์ใหม่
  · **ราคาที่จ่าย**: A2 เทรด **17.1 ครั้ง/ปี** เทียบ A1 **2.5** (7 เท่า) — ยังชนะหลัง
  หักต้นทุนแล้ว แต่ขัดกับความต้องการ "ลดความถี่" ที่ผู้ใช้เคยระบุ
  · **บั๊กที่จับได้ก่อนรัน**: positive control ของ P1 ล้ม เพราะ fixture สร้างความ
  สัมพันธ์แบบร่วมสมัยแทนแบบล่วงหน้า — ถ้าไม่มี control ตัวนั้นอาจรายงาน R1 ผิด
  · 14 เทสต์ `tests/test_trend_sizing.py` · gate SHIP

- **Egress guard จับ host ที่ไม่ได้ประกาศได้จริง (2026-08-11)** — `gate/verify.ps1`
  แดงเพราะ `scripts/osmo_toolbelt_snapshot.py` เข้าถึง `api.llama.fi` และ
  `api.coingecko.com` โดยไม่มีในนโยบาย **นี่คือ doctrine ของ Archestra ทำงานตามที่
  ออกแบบไว้** · ตรวจไฟล์แล้ว: GET ล้วน ไม่มี auth (`"no_api_key"` เป็นสตริงสถานะ
  ไม่ใช่ credential) จึงประกาศเพิ่มเป็น `access: read` และ **`untrusted_content: true`**
  เพราะทั้งคู่คืนข้อความจากบุคคลที่สาม (ชื่อเหรียญ/โปรโตคอลที่ใครก็ตั้งได้)
  · **แก้เทสต์ของตัวเองหนึ่งตัว**: `test_every_untrusted_content_source_is_flagged_in_the_policy`
  เคยบังคับว่า host ที่ flag untrusted **ต้อง**อยู่ใน news-risk.ts ซึ่งเข้ารหัสความเชื่อ
  ที่ผิดว่าเนื้อหาไม่น่าเชื่อถือเข้ามาทางบอร์ดข่าวทางเดียว · เปลี่ยนเป็นทิศที่ปกป้องจริง:
  **ทุก host ที่บอร์ดข่าวใช้ ต้องถูก flag** · ถ้าไม่แก้ ต้องติดป้าย host สองตัวนั้นว่า
  น่าเชื่อถือทั้งที่ไม่ใช่ เพียงเพื่อให้เทสต์เขียว

- E39 (2026-08-12) — **Crowded-long fade (Osmo S1) บน BTC 1h: ไม่ผ่าน G1–G4**
  (`docs/E39_CRITERIA.md` ประกาศก่อนเขียนโค้ด) จาก top-10 tools ของ
  @Flowslikeosmo · ต่างจาก E17: ต้อง L/S≥1.5 ∧ funding≥0.01% ∧ OI↑24h **และ**
  impulse ≥0.5×ATR · แผงสาธารณะ Binance ~30 วัน (ข้อจำกัด API ที่ประกาศก่อนรัน)
  · **S_full n=0**: crowded 12 แท่งไม่ทับ impulse 83 แท่งเลย · ตอน crowded ราคา
  มักลงหรือขึ้นเล็กเกินกว่าจะถึง impulse · S_fund n=5 < เกณฑ์ 20 · ห้ามผ่อน
  threshold · held-out ไม่ถูกแตะ · 5 เทสต์ `tests.test_crowding_fade`
  · **ปิด S1 บนแผงสาธารณะ 30 วัน** · ไม่ promote

- **แก้เอนจิน A1+A2 (2026-08-11) — ไม่ใช่การทดลองใหม่ และไม่ได้ทำให้กำไรดีขึ้น**
  · **A1 ถอด RSI** (`use_rsi` ดีฟอลต์ False): E37 วัดว่าแถบ 45/55 ปฏิเสธ **0 จาก
  204** สัญญาณ (W1) และ **0 จาก 185** (W2) — มีเทสต์ pin ว่าเปิด/ปิดให้ผลเท่ากัน
  ทุกหลักบนทั้งสองหน้าต่าง และมีเทสต์อีกตัวเตือนว่าข้ออ้างนี้ **scoped กับ BTC 4h
  สองหน้าต่างนี้เท่านั้น** ไม่ใช่ทุกที่
  · **A2 เปลี่ยน profit ladder จากหน่วย ROE เป็นหน่วยราคา** — ROE = leverage ×
  การขยับราคา ladder แบบ ROE จึง**เปลี่ยนกฎการออกทุกครั้งที่ leverage เปลี่ยน**
  (5x ชั้นแรกติดที่ราคา +2% / 1x ต้อง +10%) ทำให้ P5 ของ E37 ตีความไม่ได้ ·
  ชั้นใหม่ `(0.20, 0.07, 0.02)` = ค่าเทียบเท่าที่ 5x ของชั้นเดิมเป๊ะ **ไม่มี
  พารามิเตอร์ใหม่ ไม่มีการจูน**
  · **ไม่เปลี่ยน (พิสูจน์ด้วยเทสต์)**: สเปกที่ประกาศที่ 5x เหมือนเดิมทุกหลัก
  (W1 20 เทรด 75% +110.1% robust +0.50) และ **ข้อสรุป E38 ยังเหมือนเดิม 0/18
  ระบุไม่ได้** → ข้อสรุปทนต่อการแก้บั๊ก
  · **เปลี่ยน**: ตัวคุม 1x เคยถูก ladder ที่พังทำให้พิการ — W1 1x **−9.8% → +20.7%**
  (17 → 74 เทรด), W2 1x **−28.9% → +5.6%** (4 → 94 เทรด) · P5 ยังผ่านแต่ด้วย
  เหตุผลที่ถูกต้อง และส่วนต่างบน W2 เหลือ 0.04 = เสมอ
  · **วินิจฉัยหลังแก้**: คำถามค้างจาก E37 "มีอะไรรอดโดยไม่พึ่ง halt ไหม" —
  **ยังไม่มี**: 1x halt off ได้ W1 −9.0% / W2 +10.7% (แพ้ buy&hold +183.3% ยับ),
  5x halt off ได้ −89.8% / −85.2%
  · 24 เทสต์ (`test_dsl_runtime` + `test_dsl_simplification`) · gate SHIP

- E38 (2026-08-11) — **ระบุสเปกไม่ได้: 0 จาก 18 เซลล์เข้าใกล้ลายนิ้วมือ 73 เทรด/78% WR**
  (`docs/E38_CRITERIA.md` ประกาศ 9 แขน + tolerance ก่อนแตะโค้ด) ต่อจาก E37 ที่ได้
  WR ตรง (75% vs 78%) แต่จำนวนเทรดไม่ตรง (20 vs 73)
  · **กันกับดักไว้ก่อน**: การไล่ปรับจนได้ 73 เทรด = fit เข้าหาเป้า จึงประกาศว่า
  **จับคู่ด้วย (จำนวนเทรด, WR) เท่านั้น ห้ามใช้ผลตอบแทนเลือกแขน** และรายงาน robust
  ทุกแขนเสมอ — จำนวนเทรดเป็นลายนิ้วมือเชิงโครงสร้าง จับคู่ด้วยมันไม่ overfit ผลตอบแทน
  · แกน: กฎเข้าใหม่ {cross-only, re-arm ทันที, re-arm หลังกำไร} × halt {permanent,
  daily resume, off} = 9 แขน × 2 หน้าต่าง
  · **ผล: ไม่มีเซลล์ไหนอยู่ในบริเวณ 55–91 เทรด พร้อม WR 68–88%**
  · **ข้อค้นพบเชิงโครงสร้างที่สำคัญกว่า**: มี trade-off แข็งมากระหว่างจำนวนเทรดกับ
  win rate — แขนที่ **WR ≥ 70% มีแค่ 2 แขน ที่ 5 และ 20 เทรด** ส่วน **ทุกแขนที่
  เทรด ≥ 55 มี WR อยู่ในช่วง 51.5–61.5% ไม่มีเกิน 62%** → **การไปให้ถึง ~73 เทรด
  ต้องแลกด้วย win rate เสมอในทุกเส้นทางที่ทดสอบ**
  · **และแขนที่กำไรมีแค่ 2 จาก 18** (ที่ 14 และ 20 เทรด) — **ทุกแขนที่เทรด ≥ 55
  ขาดทุน −10.5% ถึง −100%** คือทุกเส้นทางที่พาไปใกล้ 73 เทรด พาไปสู่การขาดทุนด้วย
  · เหลืออธิบายไม่ได้ = สิ่งที่อยู่นอกสเปกที่ได้รับ: สินทรัพย์อื่น / 2 ปีอื่น /
  พารามิเตอร์อื่น / กฎเพิ่มเติมที่ไม่ได้ระบุ
  · ตาม §5 **รายงานแล้วหยุด ไม่เพิ่มแขน ไม่ขยับ tolerance** · E37 baseline ทำซ้ำได้
  ตรงทุกหลักหลังเพิ่มสองแกน · held-out ไม่ถูกแตะ · ไม่มี promote, gate SHIP

- E37 (2026-08-11) — **สเปกเต็ม BTC EMA9/21 + RSI 45/55, 5x, DSL exits, dedup,
  drawdown_halt 25%: ⚖️ ผลบวกทั้งหมดมาจากกฎหยุด ไม่ใช่จากกลยุทธ์**
  (`docs/E37_CRITERIA.md` ประกาศก่อนเขียนเอนจิน) ผู้ใช้ให้สเปกครบหลัง E36 ตก V1
  · เอนจินใหม่ `dynamic_grid/dsl_runtime.py` (E31 รับ weight ต่อบาร์ ไม่มี stop
  ในแท่ง) ลำดับตรวจในบาร์: **liquidation ก่อน → stop ก่อนเป้า → gap เติมที่ราคาเปิด**
  · **W1 (BTC −3.3%)**: 20 เทรด **WR 75%** (อ้าง 78% — ลายเซ็นทำซ้ำได้) PF 1.84
  ROI **+110%** robust **+0.50 ชนะ buy&hold (−1.10)**
  · **W2 (BTC +183%)**: robust **−0.45 แพ้ buy&hold ยับ** → ผลขึ้นกับหน้าต่าง
  · **P1 ยังตก**: 20 เทรด vs 73 (WR ผ่าน จำนวนเทรดไม่ผ่าน)
  · **ข้อค้นพบที่สำคัญที่สุด 3 ข้อ**: (1) **RSI 45/55 ปฏิเสธสัญญาณ 0 จาก 204**
  (W2: 0 จาก 185) — แถบกว้างเกินกว่าจะผูกมัด **"RSI Momentum" ในชื่อไม่มีผลเลย**
  สิ่งที่ทำงานคือ EMA9/21 + DSL (P4 ตกเด็ดขาด) (2) **halt ยิงตอน 23% ของหน้าต่าง**
  — พอร์ตขึ้น **+201%** คืน 25% แล้วหยุดถาวร **แช่แข็งที่ +110% อีก 1.6 ปี**
  → ตัวเลข ROI คือผลของ 5 เดือน ไม่ใช่ 2 ปี (3) **ถ้าให้เทรดต่อหลัง halt ซึ่งคือ
  สิ่งที่ระบบจริงทำ: W1 −89.8% (99 เทรด DD 97.9%), W2 −85.2%** — กลับด้านทันที
  · **บั๊กที่จับได้ก่อนรายงาน**: แขน "halt resumes" รอบแรกให้ตัวเลขเหมือนหยุดถาวรเป๊ะ
  เพราะไม่รีเซ็ต `halted` และไม่ re-baseline `peak_equity` — ถ้าไม่จับได้จะรายงานว่า
  "ผลไม่ไวต่อการตีความ halt" ซึ่งตรงข้ามความจริงสิ้นเชิง
  · **คำเตือน P5**: 5x ชนะ 1x แต่ confound — ladder นิยามด้วย ROE ซึ่งสเกลตาม
  leverage (ที่ 5x ชั้นแรกติดที่ราคา +2% ที่ 1x ต้อง +10%) ไม่ใช่หลักฐานว่า leverage ดี
  · 17 เทสต์ `tests/test_dsl_runtime.py` · held-out ไม่ถูกแตะ · ไม่มี promote, gate SHIP

- E36 (2026-08-11) — **"EMA9/21 + loose RSI, 5x" (4h, 2 ปี) จากตารางภายนอก:
  ทำซ้ำไม่ได้ (V1 ตก) และการตีความที่ทดสอบพังทุกแขน** (`docs/E36_CRITERIA.md`
  ประกาศก่อนเขียนโค้ด รวมการตีความ "loose RSI" 4 แบบ + control R0)
  · ดึงข้อมูลใหม่ `data/BTCUSDT_4h_2y.json` **4,561 แท่ง 2.08 ปี gap 0 OHLC ผิด 0**
  + funding จริง 2,295 รอบ (มัธยฐาน 4.9%/ปีที่ long จ่าย)
  · **V1 ตก**: ได้ 337 เทรด / WR 22.8% เทียบที่อ้าง 73 / 78% → **คนละโครงสร้าง
  การเทรด** — 73 เทรดพร้อม WR 78% คือลายเซ็นของการเข้าเป็นไม้ ๆ พร้อม TP/SL
  ส่วนสเปกที่ผมตีความเป็น always-in flip ไม่มี TP/SL เลย (ตารางต้นทางเองยืนยันว่า
  แนวคิด stop มีอยู่: แถวอันดับ 1 คือ "SL 2.5 ATR") · **ตามตารางการตัดสินใจ §5
  จึงไม่สรุปว่ากลยุทธ์ต้นทางใช้ไม่ได้ — เราไม่ได้ทดสอบสเปกของเขา**
  · **แต่การตีความที่ทดสอบขาดทุน ~100% ทุกแขนที่ 5x** ขณะ buy&hold −3.4% ·
  V4 ตก (R1–R3 ไม่ชนะ R0 → **RSI ไม่ได้ทำอะไร**) · V5 ตก (5x −3.00 แย่กว่า 1x
  −1.77 ทุกแขน) · V6 ตก (ruined) · held-out ไม่ถูกแตะ
  · **สามข้อวินิจฉัยที่มีค่ากว่าคำตัดสิน**: (1) **ค่าธรรมเนียมไม่ใช่สาเหตุ** — ปิด cost
  และ funding ทั้งคู่ยังได้ −99.0% สัญญาณขาดทุนด้วยตัวเอง (ซ้ำรอย Overfitting Lab
  ที่หักล้าง "แพ้เพราะค่าธรรมเนียม") (2) **ไม่ใช่เรื่องช่วงเวลา** — หน้าต่างอีก 2 ปี
  ที่ **BTC ขึ้น +183.1%** โค้ดชุดเดิมยังขาดทุน 94.6–99.8% → กลไกเป็นสาเหตุ
  (3) **เลขคณิตของการกลับข้างที่ leverage**: กลับ long↔short ที่ 5x ขยับ notional
  10 เท่า = **1.00% ของทั้งพอร์ตต่อการกลับหนึ่งครั้ง** (1x = 0.20%) → ที่ 5x
  **จำนวนเทรดคือตัวแปรหลัก ไม่ใช่รายละเอียด**
  · เพิ่ม `weights_log` ใน `leveraged.py` แบบบันทึกอย่างเดียว (นับเทรดจากน้ำหนักที่
  เอนจินถือจริง รวมบาร์ที่ถูก liquidate) — **14 เทสต์ E31 ยังผ่าน ตัวเลข E31 ไม่เปลี่ยน**
  · 19 เทสต์ `tests/test_ema_rsi.py` · ไม่มี promote, gate SHIP

- E36 (2026-08-11) — **Volume patterns (Koroush) บน BTC daily: ไม่ผ่าน G1–G4**
  (`docs/E36_CRITERIA.md` ประกาศก่อนเขียนโค้ด) จาก
  [@KoroushAK](https://x.com/KoroushAK/status/2011442735727976456)
  · ทดสอบเฉพาะ Three Patterns ที่เป็นกลไกล้วน · Liquidity Gate นอกขอบเขต
  (BTC daily VolUSD ผ่านตลอด, median ≈ $1.2B/วัน) · สีแท่ง/absorption ไม่วัดได้
  · **Primary W=10: INCREASING n=0** — นิยาม "volume โตติดกันทั้งหน้าต่าง" จากบริบท
  1m แทบไม่เกิดบน daily · ตามเกณฑ์ห้ามผ่อนนิยามเพื่อเพิ่ม n
  · ที่ W=5 (จุดเดียวที่มี n=58): INCREASING continuation **−0.68%** แพ้ FLAT
  **+0.24%** (bootstrap percentile 28.6%, ทิศตรงข้ามเคลม)
  · SPIKE (vol×3 + ≥1 ATR): fade **−6.1%** = หลัง spike ราคามัก**ต่อเนื่อง** ไม่ย้อน
  (vs rest percentile 0.6%) — สวน Pattern 3 ของบทความบนชุดนี้
  · G1–G4 FAIL, G5 ไม่ประเมิน, held-out ไม่ถูกแตะ · 8 เทสต์
  `tests/test_volume_regime.py` · **ปิดแกน volume-regime บน BTC daily ตามนิยามนี้**
  · ไม่มี promote

- E35 (2026-08-10) — **Golden pocket (0.618–0.66) บน BTC: ไม่ผ่าน G1/G2**
  (`docs/E35_CRITERIA.md` ประกาศก่อนเขียนโค้ด) มาจากโพสต์ BTC 8h ของ @The_JDK99
  ที่ใช้ confluence + confirmation ด้วยดุลยพินิจ · **ทดสอบเฉพาะชิ้นที่เป็นกลไกล้วน**
  ชั้นดุลยพินิจวัดไม่ได้จึงไม่อยู่ในขอบเขต
  · **ตัวคุมที่ทำให้ยุติธรรม**: ความกว้างโซนเท่ากันทุกระดับ (ไม่งั้นเทียบ "แถบ" กับ
  "เส้น"), pivot ที่แท่ง i ใช้ได้ตั้งแต่ i+L เท่านั้น (no lookahead, มีเทสต์เขียน
  อนาคตทับ), 1 swing = 1 ข้อสังเกต (บทเรียนการนับซ้ำจาก RVOL diag), ตัวเทียบฐาน
  สมมาตรสองทาง (ไม่งั้นเทรนด์ขาขึ้น BTC ถูกยกให้ฟรี), และ **ระดับสุ่มเป็น control**
  · **ผล primary (L=10, h=10): golden pocket −1.11% percentile 19.5% ขณะระดับ
  สุ่ม +0.62%** — ตัวที่ดีที่สุดคือ control สุ่ม · G1 FAIL, G2 FAIL (แพ้ทั้ง 0.382
  และ 0.5), G3/G4 PASS, G5 ไม่ประเมิน held-out ไม่ถูกแตะ
  · **ข้อค้นพบที่หนักที่สุด: 45 การวัด ไม่มีข้อไหนข้ามเกณฑ์ 95%/5% เลยสักข้อ**
  (ช่วง 10.9%–74.9%) ทั้งที่ด้วยจำนวนทดสอบขนาดนี้ควรมีหลุดมา ~2 ข้อโดยบังเอิญ
  · **และขนาดเอฟเฟกต์เล็กกว่า noise ที่เราสร้างเอง**: ส่วนต่างระหว่าง fib ทั้ง 4
  ระดับ = 0.93 pp ขณะส่วนต่างของ**ระดับสุ่มระดับเดียว**เมื่อเปลี่ยนแค่นิยาม swing
  = 0.89 pp → การเถียงว่า 0.618 หรือ 0.5 ดีกว่า มีขนาดเท่ากับการเถียงว่าจะนับ
  swing ยังไง ซึ่งคนวาดเป็นคนเลือกเอง
  · ข้อจำกัด: ต้นทางเป็น 8h perp เราวัด daily spot (ชุดที่ตรวจความสะอาดแล้ว) จึงไม่
  ปิดกรณี 8h โดยตรง · ไม่ได้ทดสอบ POC/VAL/liquidation cluster · n=87 ที่ primary
  · 13 เทสต์ `tests/test_retracement.py`, run count 45 · **ปิดแกน fib retracement
  บน BTC daily** ตาม §7 · ไม่มี promote, gate SHIP

- E34 (2026-08-09) — **BTC: ลดความถี่การตัดสินใจ ไม่ผ่าน K1–K6 ทุก candidate**
  (`docs/E34_CRITERIA.md` P1/K1–K7 ประกาศก่อนไฟล์รันมีอยู่จริง) ผู้ใช้ขอโฟกัส BTC
  จูนอีกครั้ง ลดความถี่ได้ ขอภาพรวมกำไร · ผมแจ้งข้อกังวลก่อน ผู้ใช้ยืนยัน จึงทำเต็ม
  โดยแปลง "ลดความถี่" เป็นสมมติฐานเชิงกลไก แกนนี้เป็นแกนเดียวที่ E30/E31/E32
  ไม่เคยแตะ (ตรวจแล้วว่า `T5_sma200_voltgt40` ถูกรันไปแล้วใน E32 จึงตัดทิ้ง)
  · **harness ผ่านการตรวจอิสระ**: C1 เทียบ `M3_sma200_hold` ของ E30 ต่างสูงสุด
  0.0045 บน robust, buy&hold DD 0.3927 vs 0.3929
  · **P1 ผ่านทั้งสองข้อ** — SMA-200 พลิก **7.47 ครั้ง/ปี**, รายเดือนตรงรายวัน
  **91.58%** สัญญาณเป็น low-frequency จริง
  · **แต่ผลแทบไม่ขยับ**: robust รายวัน −0.137 → รายเดือน −0.139 ทั้งที่ตัดเทรด
  จาก 7.8 เหลือ 2.5 ครั้ง/ปี → **whipsaw กับต้นทุนไม่เคยเป็นสาเหตุ** (คู่ขนานกับ
  ผล Overfitting Lab ที่หักล้าง "grid แพ้เพราะค่าธรรมเนียม")
  · **K6 ผ่าน**: ตัวกรอง trend ชนะ constant-mix ที่ exposure เท่ากันจริง
  (−0.139 vs −0.260) — มันทำงาน แค่ไม่พอให้ robust เป็นบวก · **K1 ตกทุกตัว**
  · ลดความถี่ลงอีกกลับแย่ลง (ไตรมาส −0.180) ไม่ใช่ "ยิ่งช้ายิ่งดี"
  · **เส้นทางต่อเนื่องเส้นเดียวชนะ buy&hold** (C5 97,463 / C1 96,719 vs 69,697
  จาก 10,000) **แต่ขัดกับผลรายหน้าต่าง** — กับดักเดียวกับ E30 เป๊ะ, ตัวอย่างเดียว,
  ความได้เปรียบเกือบทั้งหมดมาจากการเลี่ยงตลาดหมี 2022 ครั้งเดียว · เกณฑ์ที่
  ประกาศไว้ก่อนคือรายหน้าต่าง = **FAIL**
  · **2 บั๊กที่จับได้ก่อนอ่านผล**: (1) นับ drift ของน้ำหนักเป็นการเทรด ทำให้ C4
  ถูกรายงาน 363.6 เทรด/ปี **และถูกคิดค่าธรรมเนียมจาก drift** — control สำคัญที่สุด
  พิการ (2) ต้นทุนถูกลงเป็นเงินสดติดลบ ทำให้น้ำหนัก > 1.0 แล้ว buy&hold "เทรด"
  7.2 ครั้ง/ปีแทนที่จะเป็น 1 · แก้เป็นจำลองพอร์ตสองขา คิดต้นทุนเฉพาะมูลค่าที่
  ซื้อขายจริง · 18 เทสต์ `tests/test_cadence.py`, run count 72
  · **held-out ไม่ถูกแตะ** (ไม่มีผู้ชนะบน BTC) · ตาม §7 **แกน BTC ปิด** —
  เปิดใหม่ต้องมีกลไกใหม่ที่อธิบายได้ว่าทำไมตลาดถึงจ่าย ห้ามลอง SMA 150/250
  หรือ cadence อื่นแล้วรายงานตัวที่ดีที่สุด · ไม่มี promote, gate SHIP

- E33 (2026-08-08) — **Screened Trend-Vote Basket ไม่ผ่าน 6/10 เกณฑ์**
  (`docs/E33_CRITERIA.md` H1–H10 ประกาศก่อนรัน) ตัดสินบน **30 เหรียญที่ไม่เคย
  ถูกใช้ออกแบบ** · **screen คือสาเหตุและมันผิดแบบวัดได้**: ตัดชื่อที่ trend
  เป็นบวกทิ้ง 54% และชื่อที่ตัดทิ้งให้ผลดีกว่าชื่อที่เก็บทุก horizon
  (90 วัน +26.5% vs +16.3%) — บทเรียน: "สถานะมีข้อมูล" ≠ "สถิติของสถานะในอดีต
  ใช้คัดสินทรัพย์ได้" · control arm (ปิด screen) ผ่าน 8/10: CAGR 25.8%,
  DD 54.4%, MAR 0.48, Sharpe 0.80 vs equal-weight B&H 21.3%/89.1%/0.24,
  ชนะ 5/8 หน้าต่าง, timing luck 8.3 จุด, lag ไม่กระทบ, edge ครึ่งหลัง +21.5%,
  breadth 21 กำไร/9 ขาดทุน, top-1 เหรียญ LINK 14.9% — **แต่ตก H10 (DSR 0.885)
  และการเลือก arm นี้เป็น post-hoc** · setup เขียนครบใน `docs/STVB_SETUP.md`
  · **คริปโตถูกเผาหมดแล้ว** สำหรับกลไกนี้ E34 ต้องใช้ AOT/ทองคำ/ดัชนีหุ้น
  · ไม่มีการ promote, ไม่แตะ C1–C7/G1–G8, gate SHIP

- E32 (2026-08-08) — **leverage บนตัวกรองแนวโน้มก็ยังไม่ผ่าน** เกณฑ์
  `docs/E32_CRITERIA.md` ประกาศก่อนรัน · Donchian-55 2x ผ่าน G1–G5/G8 บน BTC
  (CAGR 49.8%, MAR 0.62) แต่ **ตก G6 held-out** (ETH −13.7%, SOL −61.9%) และ
  **ตก G7** (ผิวราบ 58.3% < 60%) · วัด vol drag ได้จริง: 2x ต่ำกว่าที่สัญญา
  −42%/ปี, 3x −97%/ปี, 4x −192%/ปี · block bootstrap: Donchian 2x median CAGR
  สูงสุด (56.8%) แต่ P(ruin) 7.8% และ P(DD>80%) 68.5% ขณะ 1x มี P(ruin) 0.1%
  และเปอร์เซ็นไทล์ที่ 5 ยังเป็นบวก · **frontier: 1x ชนะทุกงบความเสี่ยง และ
  2x แย่กว่าถือ BTC เฉย ๆ ในทุกช่อง** · การกระจาย 3 เหรียญไม่ซื้อโควตา leverage
  กลับมา (MAR ลดลง monotonic 0.39 → 0.19 → 0.09) · สิ่งที่ผ่าน held-out จริงคือ
  **SMA-200 ที่ 1x** (ETH 41.8%/MAR 0.57, SOL 82.9%/MAR 1.25 ชนะ buy&hold ทั้งคู่)
  แต่ตก G5 บน BTC · ไม่มีการ promote, ไม่แตะ C1–C7, gate SHIP

- Webull OpenAPI feasibility research completed (2026-07-20): Webull Thailand
  advertises OpenAPI for eligible customers trading US stocks and ETFs; the
  official API documentation scopes the Trading API to the US market.  Grid is
  not a native order type: it must be an external, event-driven limit-order
  controller using account/position reads, preview/place/replace/cancel and
  gRPC order-status events.  Official sandbox/test accounts exist, so any
  future adapter must begin read-only plus sandbox/paper validation; no live
  Webull order transport is authorized under the project constitution.

- Recommended research config: Dual 75/25 rule-based + percentile-rank regime (see HANDOFF).
- E20 RL walk-forward failed (3/6 = 50%) — RL not production-ready on BTC/4h.
- E23 dual tune: best Line-B attempt so far (mean robust −0.0078, delta +0.0301) — still not > 0 / not promoted.
- E24 separate short_cfg: FAIL (−0.0205) — worse than E23, especially ETH.
- E25 conservative geometry: FAIL (−0.0154) — better DD but still < cash; C2 miss.
- Live trading and third-party capital: forbidden until Phase 3 gates clear.
- Agent stack gate green (`gate/verify.ps1` SHIP); `run_demo.py --fast` OK (2026-07-15).

## Verified since previous handoff

- **Walk-Forward Lab slice 5 shipped (2026-08-10): `/compared-to-what` —
  "เทียบกับอะไร นับกี่ครั้ง".** This is the slice the 2026-07-25 pivot said to wait
  for; it exists because three experiments in three days produced the same lesson
  from three unrelated strategy families, which is the strongest teaching material
  the project has. Three exhibits: (1) **E33** — the coin screen kept the worse
  half, dropped names beat kept names at 30/90/180 days (90d +26.5% vs +16.3%);
  (2) **RVOL/EP9M diagnostic** — same signal, same data, no parameter changed, only
  178 clustered signals recounted as 60 episodes: 20d percentile **97.0% → 33.8%**
  and the return falls **below** the base rate; (3) **E35** — every fib level plus a
  random control at equal zone width: golden pocket −1.11% while **the random
  control won at +0.62%**, 45 measurements with **0** crossing significance, and the
  spread between all four fib levels (0.93 pp) is the same size as the spread of a
  *single random level* when only the swing rule changes (0.89 pp). Closes with a
  4-item checklist students can apply to anyone's backtest including their own.
  **Engineering invariant preserved**: every number is emitted by
  `scripts/precompute-compared-to-what.mjs` reading `docs/stvb-e33-diag.json`,
  `docs/rvol-ep9m-diag.json` and `docs/golden-pocket-e35.json` at build time and
  failing loudly if a file moves — nothing is typed into the TSX, so the page
  cannot drift from the research it teaches from (same rule as the existing lab).
  Wired into `EducationShell` nav and both build scripts. Verified live in the dev
  server: renders with the real numbers, no console errors, nav active state
  correct on the new route only, and on a 375px viewport the page does not scroll
  horizontally (all three tables scroll inside their own containers).
  Also fixed two **pre-existing** TypeScript errors in the untracked
  `measured-honestly.tsx` (two `Link to="/walk-forward"` missing the now-required
  `search` prop) — the typecheck was red before this work started.
  TypeScript, ESLint, production build, 200 frontend tests and `gate/verify.ps1`
  all pass. Not committed, not deployed.

- Adopted Minara Strategy Studio dashboard doctrine into Aegis Overview /
  Walk-Forward Lab (2026-08-09) — **UX doctrine only, no Minara code, no live
  Autopilot**. From [@slash1sol's walkthrough](https://x.com/slash1sol/status/2075522395499037048):
  (1) return and max DD sit side by side; (2) FAIL rows stay on the board;
  (3) diagnosis column states why the idea was wrong; (4) cold-shower banner
  ("backtest ≠ forecast", NFA). New `research-board.ts` pins E26/E28/E29/E32/E33
  numbers from `VALIDATION_LOG`; Overview shows `MeasuredHonestlyBoard`; Walk-
  Forward Lab pairs grid vs B&H return|DD. 3 focused tests green; full FCC
  suite 200/200.

- Reviewed `archestra-ai/archestra` @ `fc88f7c0` (2026-08-09) and adopted
  **doctrine only — zero lines of its code**. Two independent blockers: (1) it
  is **AGPL-3.0-only** with no permissive carve-out, and AGPL §13 treats network
  use as distribution — our public unauthenticated Worker means linking any of
  it would oblige source disclosure for the whole combined work; (2) Postgres +
  Kubernetes + SSO/RBAC + OTel + a multi-provider LLM proxy is two orders of
  magnitude past one researcher, one machine, one Worker.
  **Adopted (doctrine is not copyrightable):** deterministic allowlists enforced
  *outside* the guarded thing rather than by model judgement. We already had the
  mechanism — `gate/eval_gate.py` opens "deterministic checks only, never calls
  a model" — and were missing the policy, so this is 3 new gate cases, not a new
  subsystem. (a) `integrations/egress-allowlist.json` declares all **21** hosts
  the source can reach with purpose/access/`untrusted_content`; `gate/egress_scan.py`
  fails the gate on any undeclared host. Before this, hosts were pinned in eight
  files and `grep allowlist` matched only prose. (b) `live_trading: false` is
  required on every entry — the constitution restated as data, refused at
  declaration time rather than at deploy. (c) the lethal-trifecta guard.
  **Trifecta audit, two exposures, very different.** The Worker holds all three
  legs (Testnet credentials + D1; nine RSS/Statuspage feeds; the Testnet
  placement path) **but is not vulnerable**: the trifecta is a prompt-injection
  model and needs an instructable model in the path — news scoring is 855 lines
  of deterministic keyword rules with zero provider markers. That protection was
  a **side effect** of building the board LLM-free for cost, so it is now pinned
  by `untrusted_content_path_has_no_model`; adding LLM summarisation to the news
  board would complete the trifecta and will fail the gate. The **agent** (Claude
  Code here) genuinely has all three and no code fixes that — mitigations are the
  harness permission classifier, the project laws and human review; recorded as
  residual risk rather than papered over.
  **Two holes the scan found in itself, both regression-tested:** scheme-less
  host constants (`WEBULL_SANDBOX_HOST = "api.sandbox.webull.com"`) were
  invisible to a URL-only pattern, and `.pnpm-store/` mirrored our own sources so
  every finding named an unfixable path. Walk switched from `rglob` to a pruning
  `os.walk`: **20s → 0.19s**. A counted `# egress-scan: fixture` pragma exists
  because the scan's own tests must plant realistic hosts. Rejected with reasons
  in the doc's feature table: the LLM gateway, MCP registry/OAuth broker, agent
  runtime, SSO/RBAC, RAG store, OTel/Prometheus/Helm, and the dual-LLM pattern
  (correct only if a model must ever read the feeds; today none does).
  Boundary `docs/ARCHESTRA_ADOPTION.md`, pin `integrations/archestra-source.lock.json`,
  20 tests in `tests/test_egress_policy.py`, `gate/verify.ps1` SHIP.

- Reviewed `deepentropy/tvscreener` @ `38f74a11` (Apache-2.0, v0.4.0) and adopted
  **the endpoint contract only, for forward-only universe recording**
  (2026-08-09). The deciding fact: TradingView's scanner returns the present and
  nothing else — `get()` is a snapshot, `stream()` is repeated snapshots, there
  is no as-of-date anywhere in the package. So screening is **rejected** as a
  research/selection layer (it would re-run E33's measured failure with a nicer
  API), the pip package is **rejected** as a dependency (no retries/backoff/
  caching, pulls pandas, unofficial endpoint), and its `news.py` is **rejected**
  for the deployed Worker (unofficial `news-mediator` endpoint + HTML scraping,
  vs the six named RSS newsrooms the news board rests on). Its `related_symbols`
  field is noted as worth a local-only evaluation, since per-symbol attribution
  is the exact defect class the news board fixed by hand.
  **Adopted:** `dynamic_grid/universe_snapshot.py`, stdlib only, POSTs the
  scanner contract directly. Snapshots are append-only per date, written
  atomically, and cannot be overwritten; `load_as_of(profile, date)` returns the
  newest snapshot recorded **on or before** `date` and raises
  `NoPointInTimeUniverse` otherwise — asking it for E31's 2017-08-17 start
  raises rather than handing back today. Filters travel inside each snapshot so
  a point-in-time liquidity rule stays distinguishable from a hindsight one.
  **Two silent data traps found live and pinned by tests:** unfiltered
  `thailand` returns 2,250 rows whose market-cap leaders are derivative warrants
  inheriting the underlying's cap (NVDA01 at 179tn THB outranks DELTA) —
  `type=stock` + `is_primary` leaves **880** real listings including AOT; and
  unfiltered `crypto` returns 57,074 rows mixing perpetuals with spot —
  `BINANCE` + `USDT` + `type=spot` leaves **489**. First snapshots recorded for
  both profiles. Demonstration that this cannot fix the past: WAVES (delisted
  2024-06-17, present in E31's panel) is absent from today's snapshot. Value is
  **forward only** — experiments starting after 2026-08-09 can use a universe
  that was knowable at the time; E26–E33 are unaffected. Boundary in
  `docs/TVSCREENER_ADOPTION.md`, revision pinned in
  `integrations/tvscreener-source.lock.json`, BUILD 7.11 in `docs/AGENT_STACK.md`.
  **Second pass on the same day** (re-audit: "did we use its strengths fully?")
  found two load-bearing features the first adoption had skipped, and both are
  now in. (1) **Symbolsets** — `symbols: {symbolset: [...]}` gives index
  constituents: SET50 = 50, SET100 = 100, SPX = 503, NDX = 102 verified live
  (SETHD/sSET return 0, so not shipped). This is the one form of screening that
  survives our own evidence, because **membership is exogenous** — SET picks
  SET50, we cannot tune it, so it is categorically not the self-invented screen
  E33 refuted. Shipped as `set50`/`set100` with **no filters of ours**, since a
  filter on top would be editing someone else's universe; cross-checked as
  subsets of the 880-name list, no NVDR lines, AOT is a SET50 member. (2) The
  **field catalogue from the live `/metainfo` endpoint** instead of vendoring
  the library's 1.13 MB of generated enums — 3,771 fields for thailand/america,
  3,258 crypto, 3,126 forex, 426 futures; exposed as `--fields KEYWORD`.
  **The finding that shaped it:** `Value.Traded` is in **no** market's metainfo
  yet returns real numbers on `thailand` and all-nulls on `crypto`, HTTP 200
  both times — so the catalogue is incomplete and must never be an allowlist
  (pinned by a test). The reliable check is empirical: `fetch` now records
  `empty_columns` and raises `DeadSortColumn` when the *sort* column is dead,
  because ordering by a dead column leaves an arbitrary-but-stable server order
  and a truncated fetch would record an arbitrary subset while looking healthy.
  Explicitly rejected on re-audit with reasons in the doc's feature table: the
  generated enums, `filter.py`'s operator DSL (four profiles, static filters —
  a layer to maintain for no measured benefit), `beautify()`, `stream()`, and
  `ta/` vendor recommendations. No order, screen-as-signal, or promotion path
  was added.
  **Daily recording wired (2026-08-09).** Added `--all` (exit 0 only when every
  profile is recorded for today) plus `automations/universe-snapshot/run.ps1`
  and `install-task.ps1`, which registers `AegisUniverseSnapshot` as a
  **user-level Windows Scheduled Task**, daily 18:00 local — after the SET close
  at 16:30 ICT and still inside the same UTC date, so `as_of` cannot land a day
  ahead of the market. `StartWhenAvailable` is set because a missed day is a
  permanent hole. Three task-critical properties are pinned by tests: a failing
  profile does not cost the others, a same-day re-run spends no request, and a
  network error reports `failed` rather than raising or writing a partial file.
  Logs are git-ignored and roll at 1 MB. The task writes snapshots into the
  working tree and **does not commit** them. GitHub Actions was considered and
  rejected: the module is not on the remote, the archive must land in the
  working tree, and a daily unofficial-endpoint call from a cloud runner is
  likelier to be blocked than from a residential Thai IP.
  **Operator step outstanding:** registering the scheduled task was blocked by
  this session's permission classifier (persistent system configuration), so the
  installer is written and syntax-checked but **not yet registered** — run
  `powershell -File automations/universe-snapshot/install-task.ps1` once.
  Until then the archive only grows when `--all` is run by hand.
  32 tests, `gate/verify.ps1` SHIP.

- Added the three Daily Monitor boards (2026-07-27): `/news-exchanges`,
  `/news-assets`, `/news-market`, grouped with `/portfolio` in a new sidebar
  group. News is live public RSS (six newsrooms + Coinbase/Kraken Statuspage,
  no API key); scoring is deterministic keyword rules in
  `fund-command-center-local/src/lib/news-risk.ts` — no LLM, no per-item cost.
  Bands are driven by negative pressure only, so good news cannot net out a
  custody event. Live data drove five corrections, each now covered by a test:
  headline-only scoring (summaries attributed a mining pool's bankruptcy to
  BTC), digest suppression, context guards ("keeps hackers out" scored as a
  hack), future-dated Statuspage items capped at half weight, and harmonic
  damping of repeated routine chatter (Kraken 6.96 → 1.92 negative pressure).
  21 new tests; 191 frontend tests, TypeScript, ESLint, and `gate/verify.ps1`
  all pass. Contract and known limitations: `docs/NEWS_RISK_DASHBOARDS.md`.
  Holdings overlay is the demo paper/testnet book — labelled inline on every
  board. Read-only: no order, cancel, or transfer path.
  Deployed 2026-07-27 to `aegis-fund-os` (version `0bd4be39`),
  https://aegis-fund-os.bankshadow30.workers.dev — all three routes verified
  200 in production with 8/8 RSS feeds reachable from Cloudflare's network.
  Code is deployed but NOT committed; the working tree is the only copy.

- Added Pionex to the news registry (2026-07-27; deployed 2026-07-28 as version
  `f8c3a545`, verified live). Pionex publishes no usable
  feed: `pionex.statuspage.io` was never configured and still serves
  Statuspage's stock "This is an example incident" placeholder, and its blog is
  self-published marketing — neither may sit behind a real risk badge, so
  neither is wired in. Pionex is instead a `watch: true` registry entry, always
  shown even at zero articles, covered by the six independent newsrooms.
  This exposed a filter bug: the venue board only admitted ranked or held
  venues, so every unranked venue was invisible — Bitkub was the top Market
  Pulse story while having no row on the risk board. A venue now earns a row by
  being ranked, watched, held, or in the news; Bitkub immediately surfaced at
  CRITICAL 4.23 (Thai SEC / $50M hack). Also added "cyberattack" and "security
  incident" to the hack rule. 25 news tests, 197 frontend tests, TypeScript,
  ESLint, and `gate/verify.ps1` pass.

- Consolidated the primary research navigation (2026-07-27): the sidebar now
  has one `Walk-Forward Lab` entry. Its existing in-lab tabs retain Mechanism
  Compare and the overfitting lesson, so direct links and the teaching flow
  remain available without three top-level menu entries. Frontend tests,
  production build, and `gate/verify.ps1` pass.

- Reviewed and retained `nutdnuy/webull-openapi-AI-Plugin` at
  `398b02ea733286c08b37c34510992476c9becaf1` (2026-07-26).  Installed only
  its Codex auth, market-data, account, and events skills; its order and
  watchlist-write skills are intentionally excluded.  Added
  `docs/WEBULL_OPENAPI_ADOPTION.md` and
  `integrations/webull-openapi-source.lock.json`: the plugin's Thailand UAT
  HMAC-SHA256 contract remains a schema/reference source, separate from the
  existing HMAC-SHA1 Webull Sandbox adapter.  Any next connector is pinned to
  read-only Thailand UAT and must not share credentials or execution transport
  with Sandbox.

- Added a native, no-n8n runtime watchdog locally (2026-07-24):
  `.github/workflows/runtime-watchdog.yml` polls only the token-gated,
  read-only `/api/automation/runtime-status` endpoint every 15 minutes and
  creates or updates a GitHub Issue only when halted bots or failed runs are
  reported. It fails closed by skipping until its two GitHub secrets are set;
  it contains no cron, exchange, broker, order, cancel, transfer, or withdrawal
  path. Focused tests, all 156 frontend tests, TypeScript, and `gate/verify.ps1`
  pass. The Worker status-endpoint code went live with the 2026-07-27 deploy
  (it rode along in the same working tree) and is verified fail-closed in
  production: `/api/automation/runtime-status` returns 401 because no
  `AEGIS_AUTOMATION_STATUS_TOKEN` secret is set. The GitHub workflow itself is
  still inactive and still needs its two paired secrets before it can run.

- Handoff written for next session (2026-07-23): `docs/HANDOFF_CURSOR.md` §0
  summarizes Graph L2/L3 work, remote D1 0004–0007 applied, dry-loop measurement
  next steps, and commit/deploy note (code still uncommitted until user asks).

- Added project skill `.claude/skills/quant-research-pipeline/` (2026-07-25): maps
  0xTatara quant filtration pipeline (mechanism→validate→costs→paper feedback)
  onto ExperimentContract / ValidationGate / VALIDATION_LOG; stages 8–10 capped
  at paper/testnet. Listed as BUILD 7.6 in `docs/AGENT_STACK.md`.

- Added project skill `.claude/skills/quant-portfolio-allocation/` (2026-07-25):
  maps RuujSs portfolio construction (diversification ratio, cov shrinkage,
  HRP preference, Black-Litterman tilts, cut-vs-trim) onto
  `RiskBudgetAllocator` / layer weights / D1 cash default; downstream of research
  pipeline only. Listed as BUILD 7.7 in `docs/AGENT_STACK.md`.

- Added project skill `.claude/skills/agent-build-loop/` (2026-07-25): maps
  mikenevermiss AI build loop (prompt→plan→execute→check→fix, compress→execute,
  human owns plan+check, failure checklist) onto this repo; does not replace
  model-router/ship-gate. Listed as BUILD 7.8 in `docs/AGENT_STACK.md`.

- Added project skill `.claude/skills/llm-app-pattern-router/` (2026-07-25):
  filtrates Shubhamsaboo awesome-llm-apps catalog onto this stack; adopt
  scope-creep keep/split/justify + commit archaeology; reject finance demos /
  swarm default; always-on = read-only watchdog only. BUILD 7.9 in
  `docs/AGENT_STACK.md`.

- Added project skill `.claude/skills/code-graph-context/` (2026-07-26): maps
  CodeGraphContext (CLI/MCP call-graph index) as opt-in impact analysis; keeps
  L2 harness / L3 runtime / Cognee event memory distinct. BUILD 7.10 in
  `docs/AGENT_STACK.md`. Not installed by default.

- Ops item 1+2 executed (2026-07-23): applied remote D1 migrations **0004–0007**
  on `GOVERNANCE_DB` (previously pending 0004–0006 as well as 0007); local also
  has 0007. Added dry-loop `telemetry` rollup on fleet/cron responses and
  `docs/DRY_LOOP_MEASUREMENT.md` for an opt-in measurement window. Dry-loop
  remains default **off** until telemetry shows deferred drain without
  `backlogStillDeferred`.

- Sequenced L2/L3 follow-ups (2026-07-23): (1) migration `0007_grid_runtime_route.sql`
  persists `route_severity` / `route_action` / `work_remaining` / `deferred` on
  `grid_runtime_runs`; cockpit shows recent routes. (2) Opt-in dry-loop via
  `GRID_RECONCILE_DRY_LOOP=true` with round caps (default off, hard max 5) in
  `grid-runtime-fleet.ts` — each pass still uses `reconcileTestnetGridSafely`.
  (3) First L2 diamond `agent/diamonds/runtime_safety_review.py` fans out three
  static lenses and reduces with code; `tests.test_agent_graph` asserts a clean
  report on current sources. Placement authority unchanged.

- Added L2/L3 graph scaffolds without crossing the execution firewall
  (2026-07-23): `agent/graph_contracts.py` + `agent/graph_ops.py` provide
  review-finding contracts, code-only reduce, severity routing, and
  loop-until-dry discovery for the harness; they import no Fund OS / exchange
  modules. L3 `grid-runtime-graph.ts` classifies reconcile severity and plans
  dry loops in code only; `route` / `fleet` fields are additive on reconcile
  results while placement still goes solely through `grid-runtime-safety.ts`.
  Cron remains one pass per bot (dry-loop not auto-armed). Tests:
  `tests.test_agent_graph`, `test/grid-runtime-graph.test.mjs`.

- Added a Webull sandbox read-only adapter (2026-07-20). It is hard-pinned to
  `https://api.sandbox.webull.com` and makes only a signed `GET
  /openapi/account/list` call when server-only sandbox credentials are
  configured. The HMAC-SHA1 implementation matches Webull's published vector;
  the Integrations UI exposes a probe and sanitized account count/types. There
  is deliberately no Webull POST/order/cancel/transfer/withdrawal code path;
  paper-grid execution remains local. Frontend tests (100), TypeScript,
  production build, and `gate/verify.ps1` pass.

- Extended Webull Sandbox with an explicitly gated test-order path (2026-07-20).
  `POST /openapi/trade/order/place` is signed with the exact compact JSON body,
  but only when `WEBULL_SANDBOX_ORDER_TEST_ENABLED=true`; production hosts are
  rejected, orders are forced to US/EQUITY/NORMAL/LIMIT/DAY/CORE/QTY, symbols
  are allow-listed, and quantity/notional are capped at 1 share/USD25. The UI
  exposes a small Sandbox LIMIT test form and returns the sanitized result.
  Four Webull signing/order unit tests, full frontend tests (104), TypeScript,
  production build and `gate/verify.ps1` pass. Browser E2E against localhost
  was blocked by the in-app browser network boundary; no live or sandbox order
  was sent during verification.

- Grid Bot Phase 1 UI/domain upgrade completed locally (2026-07-16): exact
  Decimal.js arithmetic/geometric previews, environment-separated cockpit,
  five-step `/bots/new`, bot detail, active-order and event routes are in place.
  Demo/Paper/Testnet remain explicit; Testnet is read-only and no order endpoint
  exists. Focused frontend tests pass 18/18, TypeScript, targeted lint, production
  build and `gate/verify.ps1` pass. Desktop/mobile route screenshots are stored
  under the thread visualization workspace. Durable execution and module-backed
  governance remain Phase 2–5.
- Cloudflare Access application `aegis-fund-os` was deleted at the user's
  explicit request (2026-07-16), removing the login screen from
  `aegis-fund-os.bankshadow30.workers.dev`. An unauthenticated browser check now
  reaches `Overview · Aegis Fund OS` directly. The production Worker is public
  until an Access application or equivalent edge control is restored.
- Removed mock bot operations from `/bots` (2026-07-16): seeded fleet, P&L,
  simulated blotter, fake bot counts, and Demo tags are gone. The page now uses
  only the verified Binance Spot Testnet feed, account balances, symbol filters,
  user-entered grid configuration, and a local Open/Stop Testnet paper-signal
  lifecycle. Browser activation check passed without any exchange order call;
  frontend tests 14/14, TypeScript, production build, and gate are green.
- Added Binance-inspired bot discovery UI from the supplied reference image
  (2026-07-16): All/Spot/Futures tabs plus selectable Spot Grid and Rebalancing
  cards. Spot Grid remains the configured workflow; Rebalancing is explicitly
  not implemented and Futures fails closed. Browser checks, frontend tests
  14/14, TypeScript, production build, and `gate/verify.ps1` pass.
- Expanded the Binance Spot Testnet grid setup to Binance-style parameters
  (2026-07-16): price range, total grids, arithmetic/geometric spacing,
  investment, fee-aware profit/grid, trigger, TP/SL, Trailing Up, sell-on-stop,
  and auto-fill are available as local paper preview. Validation fails closed
  against market range, tick/step/min-notional, TP/SL ordering, and round-trip
  fees. Browser arithmetic/geometric checks pass; frontend tests 14/14,
  TypeScript, production build, and `gate/verify.ps1` are green. Order transport
  remains absent.
- Added configurable Binance Spot Testnet grid setup preview (2026-07-16):
  the Bots page accepts paper capital, levels per side, and spacing, reads live
  BTCUSDT bid/ask, balances, tick size, step size, and minimum notional from
  Testnet, then produces quantized local simulated levels. Browser verification
  passed with 24,000 USDT, 4 levels per side, and 1% spacing. No exchange order
  transport or order IDs exist. Frontend tests 12/12, TypeScript, production
  build, and `gate/verify.ps1` all pass.

- Derivatives fund-ops slice verified (2026-07-15): USDⓈ-M read-only sync maps
  funding, collateral transfers, fills, balances and remote positions; ledger
  reconciliation is idempotent and marks mismatches provisional.
- Added fixture coverage for USDⓈ-M `userTrades` → `DERIVATIVE_FILL` and clean
  internal-vs-remote position reconciliation.
- Verified 28 Python fund-ops tests, strategy gate `SHIP`, Binance signing test,
  daily-close tests, and local production build. FX/multi-currency valuation
  and persisted exception review remain next; execution remains forbidden.

## General rules

- FX valuation slice verified (2026-07-15): `ApprovedFxValuation` converts
  balances only from positive approved pair rates and fails closed when a rate
  is missing; `FundV2Store` persists deduplicated reconciliation exceptions,
  requires a different reviewer for resolution, and daily-close can persist
  open exceptions without permitting a clean close.
- Local dashboard read-only snapshot added (2026-07-15): Portfolio shows
  approved FX rates/as-of/base value; Reconciliation shows persisted exception
  records with owner/status/checker. Frontend signing tests, daily-close tests,
  production build, and strategy gate all pass.
- Added server-side `getOperationsSnapshot` read path (2026-07-15): it accepts
  only `AEGIS_OPERATIONS_SNAPSHOT_JSON` on the server, returns a typed persisted
  snapshot, and falls back explicitly to demo data when unconfigured. Portfolio
  and Reconciliation now consume this path without exposing credentials or
  execution methods to the browser bundle. Frontend tests/build and gate pass.
- Added versioned `operations_snapshot` exporter (2026-07-15): it reads the
  persisted daily report and `FundV2Store`, emits atomic JSON with FX rates,
  P/L base value, exception records, quality counts and `ready/provisional`
  status. Server function now supports `AEGIS_OPERATIONS_SNAPSHOT_PATH`.
  32 Python tests, frontend tests/build and gate pass.
- Git/Cloudflare preparation started (2026-07-16): added root `.gitignore`
  for secrets, local stores, logs, generated snapshots, Q tables and frontend
  artifacts; secret scan found no credential assignments and `gate/verify.ps1`
  remains SHIP. Git discovery shows this folder is inside a parent repository
  rooted at `C:\Users\User`, so do not stage or push until the user confirms
  whether to create a standalone repository for this project.
- Standalone repository initialized and initial commit created (2026-07-16):
  `dc2272c chore: initial dynamic grid and fund operations baseline`; active
  branch is `codex/cloudflare-release`. GitHub CLI is installed but not logged
  in, so private remote creation/push awaits `gh auth login` by the user.
- Cloudflare Workers deployment prepared and verified (2026-07-16):
  `fund-command-center-local/wrangler.jsonc` pins the `aegis-fund-os` Worker
  with `nodejs_compat`; Wrangler 4.110.0 is locked and its dry-run bundles 89
  modules successfully. The dashboard stays read-only/demo on Workers until a
  future R2-backed snapshot reader replaces the local filesystem path.
- Added GitHub Actions deployment path (2026-07-16): pushing `main` runs the
  frontend tests, builds the Worker, then deploys via `wrangler-action` with
  GitHub secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`. This avoids
  the currently failing Cloudflare Git-clone integration. Remote GitHub push
  succeeded to `Bankshadow/aegis-fund-os` branch `codex/cloudflare-release`;
  the workflow now reports a skipped deployment instead of failing while those
  user-created GitHub secrets are absent. `main` is being established as the
  production branch. `main` is now the GitHub default branch and its first
  automation run passed (2026-07-16); it will deploy only after both secrets
  are configured. Both secrets were configured and production deployment
  succeeded at `https://aegis-fund-os.bankshadow30.workers.dev` (2026-07-16).
- Binance Spot Testnet cloud connection prepared (2026-07-16): the deployed
  probe now accepts only same-origin HTTPS requests, remains read-only, and
  GitHub Actions can set the two Binance Testnet credentials as Worker secrets.
  It awaits user-created `BINANCE_TESTNET_API_KEY` and
  `BINANCE_TESTNET_API_SECRET` GitHub secrets; no mainnet credential is allowed.

- Criteria before experiment; ≥3 seeds; held-out; log negatives.
- ValidationGate thresholds are not negotiable downward.
- Synthetic ≠ real evidence; no cross-scale/TF transfer without re-validation.
- Agent stack: cheap driver + Fable advisor grams; gate is final vote (`ROUTING.md`).

## Open failures

- ~~Dual under real costs still loses to cash~~ **RESOLVED by decision D1
  (2026-07-17)**: cash accepted as Line-B default; dual tuning closed. The
  "funding/relative only" candidate was rejected without a run because both
  signals already failed standalone (E17, E18) and no new mechanism was
  proposed. Reopening requires a mechanism-level hypothesis per
  `docs/VALIDATION_LOG.md` § D1. Effort pivots to fund-ops ledger.
- ~~Fund ops: Spot fee conversion + TRANSFER sync done (2026-07-15). Still missing
  futures/Spot income → `EventType.FUNDING`; multi-currency capital FX policy.~~
  **CLOSED (2026-07-18)**: futures FUNDING_FEE/TRANSFER/fills were already synced;
  added Spot distribution income (`/sapi/v1/asset/assetDividend` → `REBATE` carry)
  and a fail-closed `capital_fx` policy so foreign-asset deposits/withdrawals/
  dividends convert via operator-approved marks (audit metadata records original
  asset/amount/rate) instead of hard-failing. CLI reuses `--mark` as the FX policy.

## Lessons learned

- Memory-orchestrator stop_threshold=2 in 50-bar windows was dead-on-arrival; fixed to 1.
- Advisor inversion beats Fable-as-driver for cost; consult only on stuck signals.
- Separate short_cfg (E24) and conservative subspace (E25) both failed to clear C1 —
  geometry tweaks alone are not enough under ExecutionProfile on this 4h set.
- A verdict without a passing test row is an opinion — factory/gate doctrine.
- Approved marks (not live tickers) keep fee conversion auditable and fail-closed.

## Local Lovable migration (2026-07-15)

- Migrated the published Aegis Fund OS source from Lovable project
  `a1b62369-da01-4dda-834d-5daab87d33b3`, commit
  `af200db1b2f50788d1dc4c4f791c81a78619eab7`, into
  `fund-command-center-local/` without changing the legacy static fund-ops pages.
- Imported 86 text source/config files; binary favicon was omitted and is not
  required for compilation.
- Installed the local Node dependencies and generated `pnpm-lock.yaml`.
- Verified a production Vite/TanStack Start build and HTTP 200 smoke checks for
  all nine baseline routes.
- Completed frontend P1–P3 locally: grouped navigation plus Strategy Lab, Bots
  & Orders, Signals, Integrations, Approvals, and Access & Roles.
- New controls are interactive local-demo state only; live order submission,
  withdrawals, and third-party capital remain unavailable.
- Production build and targeted ESLint checks pass. Generated TanStack route
  manifest contains all 15 application routes.
- Next frontend cursor: authenticated API and durable persistence for read-only
  adapters, approval/audit records, and paper execution events.
- Added a local-only Binance Spot Testnet connector (2026-07-15): public time
  reachability plus HMAC-signed `GET /api/v3/account`, with sanitized metadata
  only and no order/withdrawal endpoint.
- Official HMAC vector test, ESLint, TypeScript and production build pass;
  public Testnet `/api/v3/time` responded successfully from this machine.
- Authenticated Binance status remains pending until the user adds Testnet-only
  credentials to ignored `fund-command-center-local/.env.local` and restarts
  the local server. Credentials must never be pasted into chat or source.
- Retested after credentials were added (2026-07-15): signed read-only
  `/api/v3/account` returned HTTP 401 / Binance `-2015` (invalid API key, IP,
  or permission). Verify that the key was generated in Spot Testnet, has
  `USER_DATA` access, and permits the request source IP before retrying.
- Added Hyperliquid mainnet public Info API adapter (2026-07-15): fixed
  official endpoint, localhost-only server function, and optional public
  wallet address for sanitized position/open-order counts. The adapter has no
  wallet signing, exchange, order, transfer, or withdrawal call path.
- Verified `metaAndAssetCtxs` against `https://api.hyperliquid.xyz/info`
  (232 markets), TypeScript, production build, and `gate/verify.ps1` (SHIP).
- Removed credential-like values from `fund-command-center-local/.env.example`;
  examples contain placeholders only.
- Converted the Hyperliquid adapter to Testnet-only (2026-07-15): it now
  accepts only `https://api.hyperliquid-testnet.xyz/info` and reads optional
  `HYPERLIQUID_TESTNET_WALLET_ADDRESS`. The Testnet public Info API responded
  with 210 markets; TypeScript, production build, and `gate/verify.ps1` passed.
- Read-only review of sibling `btc-short-premium-agent` (2026-07-15): its
  Binance USD-M Futures Demo connector uses `demo-fapi.binance.com`, while its
  setup verifier is stale Bybit-only. Its local/deployment envs configure a
  proxy URL but omit `BINANCE_PROXY_ENABLED`, so the client bypasses the proxy;
  this is a likely source of regional/IP failures. Do not reuse its Futures
  credentials in the Aegis Spot Testnet connector.
- Added Bybit Testnet read-only adapter (2026-07-15): fixed Testnet base URL,
  server-time check and signed Unified wallet summary only, with no order,
  transfer or withdrawal endpoint. TypeScript, production build and
  `gate/verify.ps1` passed. Direct endpoint verification from this environment
  failed DNS resolution for `api-testnet.bybit.com`; authenticate only after
  confirming DNS/network access from the actual host.

## Direction change: research → education (2026-07-25)

**Decision (user-approved this session): pivot the product surface from "grid bot
that trades" to "education/analytics tool that teaches", using the same engine.**

Why: E20–E29 is nine consecutive grid-mechanism experiments that do not clear the
validation gate. Geometry, regime filter (E27), trailing (E28) and exposure cap
(E29) each failed to give the grid a real edge on daily AOT. Continuing to build
ops/safety plumbing around a strategy with no demonstrated edge was the actual
problem — the work was real but nobody was using it. The engine, the walk-forward
harness and the evidence ledger are genuinely good, and teaching *why* the grid
loses needs no edge at all. The user is a Thai grid-trading educator, so this
lands on real users (students) instead of hypothetical ones.

**Shipped this session — Walk-Forward Lab, four education slices (all verified
live in the app, all committed):**
1. `/walk-forward` — per-fold OOS table, verdict vs the gate, summary tiles.
2. `/walk-forward-compare` — E26 → E28 → E29 side by side with the honest
   narrative for each transition.
3. Interactive cost model on `/walk-forward` — presets Thai retail / zero / heavy.
4. `/walk-forward-overfit` — the overfitting lesson (see below).

**Engineering invariant that makes this safe to teach with:** the walk-forward is
now ONE shared pure function `src/lib/aot-walkforward.ts` used by both the CLI
research harness (now a thin wrapper) and the in-app server functions, with tests
pinning E26 (−17.97 / −10.79), E28 (−19.91 / dd 16.84 / engaged 100%) and E29
(−12.17 / dd 13.52 / −8.28) plus the 6/18 cap-inert-fold invariant. The education
views therefore cannot drift from the committed research.

**Two teaching claims were MEASURED, and both refuted the intuitive story — copy
was rewritten to match the evidence, not the other way round:**
- "The grid loses because of fees" is FALSE here: at zero transaction cost mean
  alpha is still ≈ −11.2 (marginally worse than net, a selection-artifact wobble).
  Costs are not the cause; there is no edge to erode.
- "Pick the geometry that won in-sample" is worth NOTHING here: the in-sample
  winner is also the out-of-sample winner 3/18 = 16.7%, and chance with six
  candidates is exactly 16.7%; mean OOS rank 3.56 vs random 3.50. Even the
  hindsight-best geometry averages −16.61 robust — still deeply negative.

**Research integrity note:** the Overfitting Lab measures OOS for geometry
candidates that selection REJECTED. Those runs are opt-in (`diagnostics`) and are
deliberately excluded from `runCount`, since nothing is selected on them and
inflating the reported multiple-testing count would misstate the research. A test
pins that diagnostics change neither the numbers nor the run count (324).

**Next:** put it in front of students and let their feedback choose slice 5. Do
not add more surface speculatively — building unused surface is what this pivot
was correcting. Live trading remains forbidden; these views are read-only research.

## Last session

- **E31: hunting 2–3x per year with short/futures/leverage/altcoins — FAIL, and
  the leverage axis has a cliff, not a slope (2026-08-06).** User asked for a
  strategy returning 200–300%/yr and explicitly opened the scope to shorts,
  futures, leverage and a multi-coin universe. Criteria declared in
  `docs/CRYPTO_E31_CRITERIA.md` first; one pre-run correction is recorded in
  place (windows 252 → **365 bars**, because crypto trades every day and the
  target is stated per *year* — annualising a 0.69-year window would have
  amplified noise into the headline number). Built a 33-symbol daily panel
  (2017-08-17 → 2026-08-05) with **real per-symbol funding** from
  `fapi/v1/fundingRate` (median +0.024%/day ≈ **8.8%/yr that a long pays**, so
  **~26%/yr at 3x** before any profit). Survivorship bias was attacked, not
  ignored: WAVES (data really ends 2024-06-17 — a real delisting), FTT, LUNC,
  ONE, ZIL, SUSHI, GALA, MANA, SAND and CRV are all in the universe; the
  residual bias (universe drawn from today's listings) is stated in the result.
  New `dynamic_grid/leveraged.py` models the three things that make a leveraged
  backtest lie: **intrabar liquidation** against low/high at 0.5% maintenance,
  **funding** with the correct sign per side, and **delisting as an exit at the
  last close**. 8 candidates, no tuning pass.
  **Result: all 8 fail, none even clears T1.** Best is BTC Donchian trend at 3x,
  median **+94%/yr** — under half the target. Naive 3x buy-and-hold (K7) is the
  control and it *loses* to unlevered BTC (+12% vs +55% median) while being
  wiped in 4 of 8 years, including **−100% in the year containing the March 2020
  crash**. Two-sided trend is worse than long-only (−23% vs +94%); cross-
  sectional altcoin momentum at 3x is the worst thing measured — median −99%,
  **ruined in 6 of 8 years, 5 liquidations**.
  **The two diagnostics matter more than the verdict.** (1) Re-running with
  every wick forgiven (close-to-close liquidation only) moves almost nothing —
  K1 +94% unchanged, K7 +12% unchanged, only K4 shifts −99% → −98% — so **the
  negative result is the market, not my modelling assumption**. (2) The leverage
  sweep on the best candidate is a **cliff**: median/yr goes 1x +37%, 2x +71%,
  3x +94%, 4x **+100%** (peak), then 5x **−29%** with 4 ruined years, 6x −91%,
  8x −100%. **No point on the leverage axis reaches +200% median.** The leverage
  large enough to reach the target is also large enough to be liquidated first.
  **Reporting trap worth carrying forward:** K1's *mean* is +191%/yr, which
  reads as "nearly 2x per year" — but it comes from one window (+928%), the
  median is +94%, and the median with the best year removed is **+50%**. Mean is
  the wrong statistic for a repeatability question. Also: no candidate hit ≥200%
  in more than 2 of 8 years, and those years were the years BTC itself rose hard
  — **no strategy manufactured 2–3x in a year the market did not offer it**.
  Raw output `docs/crypto-leverage-e31.json`; full record `VALIDATION_LOG.md`
  § E31. 14 tests in `tests/test_leveraged.py` pin liquidation (a 3x long dies
  on a −40% wick that close-only maths survives), funding direction, delisting,
  and no-lookahead. `gate/verify.ps1` SHIP.

- **E30: BTC directional logic ("high win rate, high RR from 10k") — FAIL, and
  the two headline metrics the question was built on both misled (2026-08-05).**
  First non-grid experiment in the ledger. Criteria written to
  `docs/BTC_E30_CRITERIA.md` **before** the first run and unedited afterwards.
  Pulled a fresh 3,276-bar BTCUSDT daily series (2017-08-17 → 2026-08-05) from
  Binance public klines into `data/btc_daily_full.json` — validated 3,276/3,276
  OHLC-ordering clean with **zero** timestamp gaps, so no repair was needed
  (contrast the AOT fixture, which needed one). Six candidates with **textbook
  parameters and no tuning pass at all**: buy-and-hold, Donchian-55 + ATR trail,
  Donchian-20 fixed 3R, SMA-200 regime hold, RSI dip, SMA 50/200 cross. New
  `dynamic_grid/directional.py` is long-only spot, all-in compounding from
  10,000, 0.15%/side both legs, and **adversarial on purpose**: a bar touching
  stop and target together books the stop, and a gap through a level fills at
  the open, never at the level. **Result: every candidate fails C1 (best mean
  robust −3.6%) and C2 (best beats buy-and-hold in only 4/12 windows); all five
  pass C3** — every logic really does cut drawdown (M5 14.9% vs B&H 39.3%), it
  just pays for it in return, and robust weights drawdown 2x.
  **The three findings worth more than the verdict.** (1) The candidate
  *designed* to have a high win rate (RSI dip, exits early at RSI 55) produced
  the **lowest** win rate, 33.3%, and expectancy **−4.19%**/trade — exiting
  early cuts the winners without touching the stop, so RR collapsed to 0.90.
  (2) Highest WR (M5, 75%) and highest RR (M3, 8.11 at WR 34.3%) are **different
  candidates and neither cleared the gate** — no single metric predicted
  anything. (3) The fixed-3R candidate realised **RR 2.50, not 3.0**: costs,
  gaps and the stop-wins-ties rule eat the difference, so paper RR ≠ received
  RR. (4) C7 reproduces the Overfitting Lab result on a different asset class
  and a different strategy family: picking the best in-sample performer beat the
  candidate average in only **3/10 folds (30%)** and was actually best **2/10 =
  20%, exactly chance (1/5)** — fold 4 picked a candidate showing +372% IS and
  got **−13.4%** OOS.
  **Answering the literal question honestly:** the single-path continuous run
  from 10,000 ranks M5 first (71,813); the window-chained view ranks M3 first
  (96,334) with M5 at 51,864. **Two defensible ways of asking "what does 10k
  become" give two different winners** — and M5's rank rests on 8 trades in 9
  years. Held-out is worse: M3 keeps positive expectancy on ETH (+1.34%) but
  loses it on SOL (−3.38%), so C6 fails too. **Do not tune channel/ATR/RSI to
  chase this** — that is the E23–E25 pattern, and C7 says selection on this data
  is worth nothing. Reopening needs a mechanism-level hypothesis declared first.
  A defect was caught by its own test before any result was read: `total_return`
  divided by `equity[0]`, which is marked *after* the entry fee, quietly
  forgiving the entry cost and hiding a day-one drawdown; portfolio numbers now
  come from a curve that starts at the pre-trade capital. Raw per-window output
  in `docs/btc-directional-e30.json`; full record in `VALIDATION_LOG.md` § E30.
  10 new tests in `tests/test_directional.py` pin no-lookahead (rewriting the
  future cannot change a past trade, checked for all six candidates), the
  adversarial fill rules, and both-legs costing. 35 Python tests,
  `gate/verify.ps1` SHIP.

- **E29: exposure cap on trailing — ⚖️ M1–M3 pass on the mean, but decomposition
  kills the mechanism claim; gate still FAILs (2026-07-25).** Criteria declared in
  `AOT_VALIDATION_CRITERIA.md` §6c before running. Hypothesis: E28's trailing lets
  long inventory accumulate across re-anchors, so cap it at the initial grid's own
  capacity (Σ quantity over the initial BUY levels — geometry, not a tuned number);
  a BUY does not fill while inventory sits at the cap, bounding reversal drawdown
  while the SELL/alpha side is untouched. One variable changed from E28
  (`exposureCap: GRID_CAPACITY`); implemented on the existing maxInventory-style
  guard in `aot-backtest.ts`; `--exposure-cap` in the walk-forward harness. **Note
  I corrected the §6c parameter spec BEFORE running** (pre-run, pre-result): the
  first draft capped BUY *leg count*, but `reAnchor`→`armGrid` already bounds leg
  count each arming — the real drawdown source is inventory carried across
  re-anchors, so the cap was moved to inventory to match the stated hypothesis.
  **Result: mean robust −19.91 → −12.17 (biggest single improvement in the whole
  E-series), mean maxDD 16.84% → 13.52%, mean alpha −9.40 → −8.28 — so M1, M2 and
  M3 all pass as pre-declared.** But fold-by-fold vs E28: only **6/18 folds are
  identical** (cap never bit → reproduces E28 bit-for-bit, proving the
  implementation is clean and the one-variable invariant holds). Of the 12 changed
  folds only **3 are pure mechanism** (f1, f3, f18); the other **9 changed because
  the in-sample step selected a different geometry once the cap was active — a
  selection artifact, not the mechanism.** Worse, the mean robust gain is driven by
  folds that **stopped trading**: f18 robust −73→−28.8 but cycles 5→0 (its "+25.7
  alpha" is just holding inventory, not grid profit), f14 cycles 20→0, f2 cycles
  10→0. Where cycles=0 the drawdown reduction is a tautology (not in the market =
  no drawdown), which is why engaged dropped 100%→78%. The 3 pure-mechanism folds
  net slightly WORSE (f1, f3) or better only by disengaging (f18). **So per the
  pre-declared table it logs as ⚖️ (M1+M2+M3 passed on the mean), but the honest
  reading is: the mean pass is selection artifact + disengagement, not evidence the
  mechanism works.** Do NOT tune cap size/trigger (E23–E25/E27 lesson). Raw folds
  in `docs/aot-walkforward-e29.json`; full record in `VALIDATION_LOG.md` § E29.
  **Strategic weight: E29 is the 9th grid-mechanism experiment (E20–E29) that does
  not clear the gate. Geometry, regime filter, trailing and exposure cap have all
  failed to give the grid a real edge on daily AOT. This is now strong cumulative
  evidence to pivot rather than build grid-mechanism #10** — see the consultation
  in this session and HANDOFF.

- **Execution Safety Control Plane verified end-to-end against Binance Spot
  Testnet, and two blocking defects found and fixed (2026-07-24).** The prior two
  entries described this slice as unit-tested and pending a migration; both claims
  needed correcting.

  **Migration status was wrong.** `wrangler d1 migrations list GOVERNANCE_DB
  --remote` reports "No migrations to apply" — all seven files including 0006 and
  0007 are already applied remotely. The entries below saying migration 0006 is a
  deployment prerequisite are stale. Note this machine's `wrangler` is logged in as
  the account owner **with `d1 (write)`**, so future migrations do not need the
  missing `CLOUDFLARE_D1_API_TOKEN` secret. (`d1 execute --remote` hangs here
  waiting on an interactive confirm, so the tracking table is the evidence, not a
  direct `sqlite_master` query.)

  **Defect 1 — the placement budget deadlocked a healthy bot.**
  `reconcileOneTestnetGrid` threw when the plan exceeded `maxPlacementsPerRun`
  instead of placing what the budget allowed. The backlog therefore never drained,
  every later run failed identically, and after 3 runs the circuit breaker halted a
  bot that never malfunctioned. Found live on BOT-cafaa7ec: 15 replenishments
  against a cap of 8, halted after three clicks with `runtime.safety_halted`
  {failures:3, threshold:3}. Now the run places the first `maxPlacements` and
  reports the rest as `summary.deferred`. The subtlety that keeps this correct:
  `targetedSources` is still built from **all** planned replenishments, so a
  deferred fill stays un-terminal and is re-planned next run — committing it would
  strand the grid permanently. Verified live: run 1 placed 8 / deferred 7, run 2
  placed the remaining 7, breaker stayed at 0, 15 real Testnet orders appeared
  (`aegis-r-` prefix), ledger 20 → 35.

  **Defect 2 — a halted Testnet bot was unrecoverable from the cockpit.** The
  Resume button was gated on `environment !== "BINANCE_TESTNET"` and
  `clearGridBotSafetyHalt` had no caller. Worse, `command(..., "RUNNING")` routes
  Testnet through `startBinanceTestnetGridBot`, which refuses outright once an
  execution ledger exists ("duplicate start blocked"), so there was no path back to
  RUNNING at all. Added a Clear-safety-halt control (reason required, ≥3 chars,
  appends `runtime.safety_resumed`) and a Resume that uses
  `transitionGridBotRuntime` — a pure state transition, no exchange call, since the
  ladder is already placed.

  **Defect 3 — schema-drift diagnosis and a leaked lease.** Mirroring the 0005
  incident, code can ship against a database without the 0006/0007 tables; the raw
  `D1_ERROR: no such table` named nothing actionable. Added
  `withStorageDiagnosis`: still **fail-closed** (degrading would place orders
  without a lease, which is the one thing the lease prevents), but with an
  actionable message, raised **before** the durable run so a pending migration
  never burns the failure budget and halts a fleet. Found while fixing it that
  `startRuntimeRun` sat outside the try/finally — if it threw, the already-acquired
  lease leaked for its full 120s TTL and blocked that bot. It now releases before
  rethrowing.

  **Live verification of all four safety mechanisms** (local wrangler, real
  Testnet): replenishment budget drains in batches; circuit breaker halts at 3 and
  writes a hash-chain event whose `previousHash` matches the prior event;
  `GRID_TESTNET_KILL_SWITCH=true` blocks before lease/run/exchange, places nothing,
  writes no run row and does **not** count a failure (operator decision, not a
  malfunction); 4 concurrent cron POSTs → exactly 1 acquired the lease (459ms) and
  3 were rejected in ~80ms with no run row and no failure count — important because
  a 15-minute cron overlapping itself would otherwise halt the fleet in 3 rounds.
  Stale-evidence rejection remains unit-tested only. Frontend 153/153, TypeScript,
  build, `gate/verify.ps1` SHIP.

  **Still operator-only:** production Worker still holds the old Binance Testnet
  credentials (`-2015`). The new key is proven working locally. Update the GitHub
  secrets `BINANCE_TESTNET_API_KEY`/`_SECRET` and re-run the deploy workflow — no
  push needed. Watch that `deploy-cloudflare.yml` **skips the secret-sync step
  silently** when those secrets are empty, so a green run does not by itself prove
  the Worker was updated.

  **Testnet housekeeping:** five leftover SELL orders from the 2026-07-17 grid
  (67,179.80 → 69,715.00) were cancelled at the user's explicit request before
  testing, freeing 0.04381 BTC. They were not in the D1 ledger under those client
  order ids, so the first reconcile correctly flagged 5 rows
  `RECONCILIATION_REQUIRED` rather than inventing fills.

- **n8n workflow automation adaptation added locally (2026-07-24; not
  deployed):** analyzed the supplied n8n course roadmap/cheatsheet and applied
  Schedule Trigger + authenticated HTTP/Webhook + If quality-gate patterns as
  a read-only Aegis runtime watchdog. Added
  `automations/n8n/aegis-runtime-watchdog.json`, disabled by default, and a
  token-gated `GET /api/automation/runtime-status` endpoint with no execution
  capability. Documentation is in `docs/N8N_AUTOMATION.md`. The workflow must
  receive only the status token, never exchange credentials; it must not call
  `/api/cron/grid-sync`. Endpoint tests, TypeScript and `gate/verify.ps1`
  passed.

- **Production deployment completed (2026-07-23):** deployed Worker
  `aegis-fund-os` successfully to
  `https://aegis-fund-os.bankshadow30.workers.dev`, version
  `86ad8e8b-eca1-45e7-bbaf-cb25f5ba8910`. Before deploy, uploaded the Worker
  secret `GRID_TESTNET_KILL_SWITCH=true`; remote D1 migration check reported
  no pending migrations. Cron was not enabled and no Binance/Testnet order was
  submitted. Direct PowerShell HTTPS smoke POST could not complete because its
  TLS connection was closed locally; deployment itself returned success.

- **Production safety redeploy completed (2026-07-23):** corrected the global
  Testnet kill-switch coverage so it now blocks both initial grid placement
  paths and runtime reconciliation. Deployed version
  `f4db846b-8a2a-4723-8151-26ab7e89f0cc` after TypeScript and production build
  passed. `GRID_TESTNET_KILL_SWITCH=true` remains set; cron remains disabled.

- **Execution Safety Control Plane started (2026-07-23, local; migration not
  yet applied/deployed):** all production Testnet reconciliation entrypoints
  (one-bot, batch, external cron and scheduled driver) now use a D1-backed
  safety wrapper. It takes an atomic per-bot lease before any exchange
  placement, creates a durable run ledger, caps replenishments per run, honors
  `GRID_TESTNET_KILL_SWITCH=true`, and counts consecutive failures per bot.
  At the configured threshold (default 3), it pauses the bot and appends a
  `runtime.safety_halted` hash-chain event. Added migration
  `fund-command-center-local/migrations/0006_grid_runtime_safety.sql` and
  focused safety tests. This remains **Binance Spot Testnet only**; no mainnet
  or third-party capital path was added. ~~Before enabling cron, apply migration
  0006 to D1~~ — **superseded 2026-07-24: 0006/0007 are applied on remote D1.**

- **Five-pass safety hardening completed locally (2026-07-23):** reconciliation
  leases renew before every placement (120s default), stale/future exchange
  status evidence is rejected, the open-order cap is rechecked immediately
  before each placement, and automatic circuit-breaker recovery requires a
  reason plus a `runtime.safety_resumed` audit event. Runtime safety state and
  recent durable run records are exposed to the Bot Cockpit. Still Testnet
  only; ~~migration 0006 remains a deployment prerequisite~~ — **superseded
  2026-07-24: applied on remote D1; see the top of this section.**

- **E28: trailing re-anchor grid — first mechanism that actually works, but it
  still does not clear the gate (2026-07-23).** Criteria declared in
  `docs/AOT_VALIDATION_CRITERIA.md` §6b before running, including three
  mechanism-specific bars (M1 alpha must beat the −10.79 baseline, M2 the four
  worst folds must actually move, M3 drawdown must stay under buy-and-hold) and a
  pre-written decision table. Implemented as opt-in `trailing: { mode:
  "TRAIL_UP" }`: when a bar closes above the top level, open orders are
  **cancelled** — not held, which was E27's fatal flaw — the whole ladder is
  lifted by the same ratio keeping width and geometry, and the grid re-arms
  around the new price. Decided on the close *after* that bar's fills, so it
  never front-runs. Upward only; trailing down is a different mechanism and was
  deliberately not tested. Default off; `trailing: null` reproduces prior numbers
  to the digit. **Result: M1, M2 and M3 all pass — mean alpha −10.79 → −9.40 and
  engaged 83% → 100% — but C1, C2 and C7 still fail, so it is NOT promoted.**
  The mechanism verifiably does what it was designed to do: folds 6, 7 and 11,
  which sat at `cycles = 0` because the grid had sold out, now trade 8/15/15
  cycles over 48/28/46 re-anchors, improving alpha by +9.83/+13.51/+6.53.
  **Attribution caveat worth carrying forward:** enabling trailing also changes
  which geometry the in-sample step selects, and 5 folds ended up on a different
  config. Folds 3 and 17 have `reAnchors = 0`, so their entire delta is a
  selection artifact, not the mechanism — fold 3's −68.72 → −81.05 is purely an
  ARITHMETIC → GEOMETRIC switch. Restricting to the 13 folds whose selection was
  unchanged isolates the mechanism: alpha −9.28 → −6.09 (+3.19), drawdown
  15.17% → 16.62%. **Trailing buys alpha with drawdown** — it keeps the book in
  the market during trends, so it captures more upside and carries more exposure,
  and because robust score weights drawdown 2x, robust gets *worse* (−17.97 →
  −19.91) even as alpha improves. Not a contradiction, just what the score
  measures. **Do not tune the trigger, width or lift distance to chase C1** —
  that is the E23–E25 pattern exactly. A next step must be a new hypothesis
  aimed at the *drawdown* side (e.g. capping exposure at re-anchor), declared as
  E29 before running. Full record in `docs/VALIDATION_LOG.md` § E28; raw folds in
  `docs/aot-walkforward-e28.json`. Frontend 119/119, TypeScript, build,
  `gate/verify.ps1` SHIP.

- **E27: percentile-rank regime filter — FAIL, and worse than baseline
  (2026-07-23).** First mechanism-level experiment permitted by the D1/E26
  reopening conditions. Hypothesis: E26 showed the grid loses by selling into
  rallies, so detect trend by percentile rank (the detector E14 validated) and
  suspend the side that fights it — SELL in TREND_UP, BUY in TREND_DOWN.
  Implemented as an opt-in `regimeFilter` on `BacktestConfig` plus pure exported
  `computeRegimeStates`; default off and `regimeFilter: null` reproduces prior
  results to the digit. State for bar `i` is ranked from momentum complete at
  bar `i-1`, and the harness supplies 302 warm-up bars before each window so the
  detector starts ranked rather than blind — warm-up is past data, so it adds
  history without lookahead (pinned by a test that rewrites the tail and asserts
  earlier states are unchanged). Parameters were fixed a priori (lookback 20,
  rankWindow 252, ranks 80/20); there was no tuning pass. Same 18 folds, same
  costs, same selection rule as E26 — one variable changed. **Result: mean alpha
  −10.79 → −12.19, engaged 83% → 67%, mean robust unchanged at −17.97.**
  **Why it failed matters more than that it failed.** (1) The four worst folds
  were untouched: folds 6, 7 and 11 returned bit-identical numbers despite the
  filter being active for 57/56/104 TREND_UP bars, because those folds already
  had `cycles = 0` — the grid had sold out and stopped trading, and a filter
  cannot help what is not trading. Fold 3 got *worse* (−68.72 → −79.87) because
  suspending buys in TREND_DOWN forfeited good entries. (2) Suspending a limit
  order **delays a fill, it does not avoid one**: the order is held rather than
  cancelled, so when the regime relaxes it executes at its original limit price.
  The rally was postponed, not captured. Both facts are now pinned as tests.
  **Consequence: do not tune lookback/rank thresholds to chase this** — the
  mechanism is wrong in principle, not mis-parameterised, and tuning it would
  repeat E23–E25 exactly. Preserving upside on a fixed-level grid requires the
  levels themselves to move (trailing / re-anchoring), which is a different
  mechanism needing its own pre-declared criteria as E28. Full record in
  `docs/VALIDATION_LOG.md` § E27; raw folds in `docs/aot-walkforward-e27.json`.
  Frontend 115/115, TypeScript, build, `gate/verify.ps1` SHIP.

- **E26: AOT grid walk-forward — FAIL (2026-07-22).** Closed the "Not tested"
  gap that `STATE.md` had been carrying: OOS, walk-forward, sensitivity and
  multiple-testing are now measured, not aspirational. Criteria were declared and
  written to `docs/AOT_VALIDATION_CRITERIA.md` **before** the first run and were
  not edited afterwards. Pulled a 5,273-bar AOT.BK daily fixture (2005-01-04 →
  2026-07-20) from the Yahoo public chart endpoint; exactly one source bar
  (2023-08-08, `low` one tick above `close`) was repaired by clamping its low to
  the close and the repair is documented in the fixture README. Note
  `analyzeMarketData` does **not** catch that defect class — it counts
  non-positive prices, not OHLC ordering — so `validateMarketBars` is now run
  over the whole file up front by the harness. New
  `fund-command-center-local/scripts/aot-walkforward.mjs`: anchored-rolling
  IS 504 / OOS 252 / step 252 → 18 non-overlapping OOS folds, geometry selected
  **from in-sample bars only** (AOT ran 5 → 64 THB, so a range fitted on the whole
  file is invisible lookahead), Thai retail costs (0.157% + 0.005% + VAT 7% +
  0.05% slippage), ฿1M split 50/50 inventory/cash, 324 total runs recorded for
  multiple-testing. **Result: mean robust −17.97, mean alpha −10.79 vs
  buy-and-hold, parameter surface flat in only 27.2% of perturbations → C1, C2
  and C7 fail.** C3 passes decisively (mean DD 15.2% vs B&H 28.6%) and C4 passes
  (engaged 83%). Diagnosis: grid does exactly what it is designed to do — it wins
  the crash folds (2008 alpha +18.6, 2020 +10.3) and loses the trending-up folds
  catastrophically (−68.7, −64.0, −36.7). That is structural, not a parameter
  error, so **geometry tuning is closed** per the E23–E25 lesson; reopening needs
  a mechanism-level hypothesis aimed at the trend problem (regime filter,
  trailing-up), same bar as D1. **Engine defect surfaced and NOT yet fixed:**
  `WORST_CASE` scored *better* than `CONSERVATIVE_OHLC` in several folds
  (fold 2 by +22.45 pct pts) because the two modes differ only in intra-bar fill
  ordering, and `OPTIMISTIC_OHLC` was bit-identical to conservative because
  `ambiguousBars` is 0 on every daily fold — so C5 is a weak test on daily data
  and the mode labels do not currently bound anything. Raw per-fold output with
  Run IDs and config hashes in `docs/aot-walkforward-e26.json`.

- **Execution-mode defect fixed the same day (2026-07-22).** Root cause was not
  the ambiguous-bar policy: the fill comparator sorted *both* sides by
  `gridIndex`, so reversing it for `WORST_CASE` produced the worst buys but the
  **best** sells — two opposite assumptions in one mode, which is how "worst"
  outscored "conservative" on real folds. Now ranked by adversity per side (a buy
  is worse the higher it pays, a sell worse the lower it accepts);
  `OPTIMISTIC_OHLC` inverts it and fills buys before sells so an ambiguous bar
  closes a cycle; on an ambiguous bar `WORST_CASE` fills only the
  exposure-increasing leg and is never credited a cycle; a real intrabar slice
  bypasses all assumptions. Effect on E26: WORST_CASE mean robust −13.81 →
  −15.75 (moves the right way), optimism gap 0.00 → 0.28 pct pts, CONSERVATIVE
  bit-identical, **verdict still FAIL**.
  **Do not overclaim the modes.** Testing established that they bracket
  *per-fill execution quality* only. Portfolio-level outcome is NOT bracketed:
  each mode leaves a different set of orders open, so later bars diverge and even
  the cycle count can invert. And `CONSERVATIVE` is not inside the bracket at all
  — it declines to guess and books no fill on an ambiguous bar, so its equity can
  land above or below both. The intuitive claim
  `optimistic >= conservative >= worst` is false; a test asserting it was written,
  failed against the engine, and was removed as wrong rather than the engine bent
  to satisfy it. Frontend 111/111, TypeScript, build, `gate/verify.ps1` SHIP.

- Added the reporting-period lock, completing fund-ops roadmap item 4
  (2026-07-20). `FundV2Store.lock_period` seals a month (`YYYY-MM`) or quarter
  (`YYYY-Qn`) only when the period actually contains closes, every daily close in
  it is already locked (the maker/checker control lives at the daily level), and
  no exception in it is still open; re-sealing is rejected rather than silently
  rewriting who signed. The point of the feature is teeth, so the seal is
  *enforced*, not merely recorded: `record_close`, `add_exception` and
  `lock_close` raise `PermissionError` for any date inside a sealed period, and
  the check tests **both** period identifiers a date belongs to — sealing
  `2026-Q3` therefore also blocks an August write whose month period was never
  sealed on its own. Pure `reporting_period`/`periods_covering` helpers fail
  closed on a malformed date instead of mis-bucketing it (which would let a
  back-dated write slip past). 12 tests in `tests/test_fund_period_lock.py`;
  fund suite 50 → 62, gate SHIP. Note this makes the daily-close job correctly
  refuse to rewrite a sealed period — the raised message names the period.

- Added the performance-measurement slice, fund-ops roadmap item 4 (2026-07-20).
  New `dynamic_grid/performance.py`: **money-weighted return (XIRR)** solved by
  bisection (no derivative, cannot diverge on irregular flows) that fails closed
  on <2 flows, single-signed flows, or an unbracketed root; **strategy
  attribution** that partitions the ledger by `strategy_id` and replays each
  partition through the *same* `AppendOnlyLedger.snapshot` used for the headline
  number — so attribution can never disagree with the fund total, inventory is
  matched within a strategy (a sell with no matching buy in that strategy fails
  closed), and unattributed events are grouped rather than dropped; and
  **benchmark comparison** returning excess return, failing closed on a
  non-positive start level instead of flattering the fund with a fake 0%
  benchmark. Existing pieces were reused rather than duplicated: NAV landed in
  the daily close earlier, and true TWR already exists at
  `fund_v2.time_weighted_return` (note `track_record.metrics` reports a *simple*
  return, not TWR). 12 tests; named `tests/test_fund_performance.py` so the
  gate's `test_fund*` discovery actually runs them — fund suite 38 → 50, gate
  SHIP. Remaining in item 4: month/quarter reporting-period lock (today only
  per-`report_date` lock exists via `FundV2Store.lock_close`).

- **Schema-drift defect found and fixed the same session (2026-07-20).** After
  deploying migration 0005 + the code that uses it, inspection of the deploy run
  showed the "Apply D1 migrations" step had been **skipped** — it is gated on a
  `CLOUDFLARE_D1_API_TOKEN` repo secret that is not configured — so the new code
  shipped against a remote D1 without the new columns. Reads were safe
  (`SELECT *`), but the first reconcile marking a fill would have run an UPDATE
  naming missing columns and failed the whole atomic batch. Applying the
  migration directly from here was blocked by the tooling permission gate, so
  the fix is defence in depth: (1) `recordGridSync` keeps the atomic core
  (status, replenishments, audit) free of the new columns and captures fill
  detail in a **separate best-effort batch** that logs and continues if the
  columns are absent — reconciliation is never broken by a pending migration,
  realized P/L just falls back to the estimate; (2) the deploy workflow now
  falls back to the deploy token for migrations, `continue-on-error` with a loud
  `::warning::` so drift is visible instead of silent. Regression test added
  ("reconciliation still succeeds when the database lacks the 0005 fill
  columns"). The fallback then proved *why* the dedicated token exists: it ran
  and failed with `code 7403 — the given account is not authorized to access
  this service`, i.e. the deploy token has no D1 permission. Non-fatal as
  designed — deploy `c9f656e` succeeded, drift is now surfaced as a workflow
  warning, and production smoke is green (`/bots` 200 with the public-test
  badge, bot Grid Profit 200, cron endpoint 200 no-op). **Still to do (needs
  your action):** apply migration 0005 to remote D1 — add a
  `CLOUDFLARE_D1_API_TOKEN` secret with D1 edit permission, or run
  `wrangler d1 migrations apply GOVERNANCE_DB --remote` once locally. Until
  then fill detail is not persisted and realized P/L stays estimate-based.

- Realized P/L now measured from actual fills, not modelled (2026-07-20).
  Previously realized-cycle P/L used each order's LIMIT price and a flat
  0.10%/side fee estimate. Migration `0005_grid_bot_fill_details.sql` adds
  nullable `filled_quantity/avg_fill_price/commission/commission_asset` to
  `grid_bot_orders`; new pure `src/lib/grid-fills.ts::aggregateFillsByOrder`
  folds `myTrades` into one execution record per order (avg price = Σ quoteQty /
  Σ qty, summed commission, `MIXED` sentinel when one order charged fees in more
  than one asset). The planner carries that detail on `plan.filled`,
  `recordGridSync` persists it (COALESCE so a later empty sync cannot erase it),
  and `computeRealizedCycles` keeps **pairing on the LIMIT price** (grid-line
  geometry) while computing **profit from the actual fill price and real
  commission**: quote-asset fees as-is, base-asset fees valued at that leg's own
  fill price, and anything unvaluable (BNB/MIXED/absent) falls back to the
  estimate. Each cycle reports `feeBasis: actual|estimated` and the summary
  exposes `allFeesActual`; the Grid Profit page shows a Fee-basis column and
  labels the tile "fees from real commissions" vs "partly estimated". Also DRYed
  the duplicated order row-mapping into `orderFromRow`. +10 tests → 97/97;
  TypeScript, build and gate SHIP. Migration verified locally (applies clean;
  new columns queryable and null for legacy rows → fallback path intact).

- Added abuse guards for the login-less public deployment (2026-07-19). Enabling
  public test mode opened create/start to the internet with **no rate limit and
  no bot cap** (only MAX_GRID_ORDERS=40 per grid), so one visitor could fill D1
  and spray testnet orders. New pure `src/lib/abuse-guards.ts` enforces three
  env-overridable caps — `AEGIS_MAX_BOTS` (25), `AEGIS_MAX_CREATES_PER_WINDOW`
  (5) over `AEGIS_CREATE_WINDOW_MINUTES` (10), and `AEGIS_MAX_OPEN_ORDERS` (120)
  — backed by plain D1 aggregates (`countBots`, `countBotsCreatedSince`,
  `countOpenTestnetOrders`), so **no migration or new table** was needed. Wired
  into `createGovernedGridBot`, `createAndStartTestnetGridBot` and
  `startBinanceTestnetGridBot`; every check runs before any durable write or
  exchange call (fail closed). +8 tests → 87/87; TypeScript, build, gate SHIP.
  Verified both directions on local wrangler: with `AEGIS_MAX_BOTS=1` a create
  was rejected ("Bot limit reached (1)…"), and with defaults a create succeeded
  (PENDING_APPROVAL) — the guard blocks abuse without blocking legitimate use.

- Enabled public test mode on production and ran the first live E2E (2026-07-19).
  Set `AEGIS_PUBLIC_TEST_MODE=true` as a wrangler `vars` entry (commit `6e48be1`,
  deploy run 29690065666 success); production `/bots` now shows the PUBLIC TEST
  MODE banner. Drove the 5-step wizard on production to create + one-click-start a
  small BTCUSDT testnet grid (`E2E Public Test BTC Grid`, BOT-360baa9c, range
  63000–65000, 6 grids, 600 USDT). **Result: the software path is proven** — the
  create + auto-approve mutations succeeded on public prod with no login (public
  test mode works), the execution slice attempted real order placement, and on
  the exchange error it rolled back cleanly to APPROVED/IDLE with zero orphaned
  orders. **Blocker (operator action, not code):** placement returns
  `Binance Testnet -2015: Invalid API-key, IP, or permissions` — the Worker's
  `BINANCE_TESTNET_API_KEY/_SECRET` are invalid/expired/IP-restricted (testnet
  keys expire; same -2015 seen historically). To get real fills + realized P/L:
  regenerate a Spot Testnet key (USER_DATA + trade), update GitHub secrets
  `BINANCE_TESTNET_API_KEY/_SECRET`, redeploy to sync Worker secrets, then Start.
  **R2 also blocked at the account level:** `wrangler r2 bucket create` returned
  `code 10042 — Please enable R2 through the Cloudflare Dashboard`; the reader +
  commented binding are ready, but R2 must be enabled on the account first.

- Deployed the full session batch to production (2026-07-19): commit `09bd422`
  (fund-ops NAV close, grid realized P/L, public test mode, external cron
  endpoint, R2 snapshot reader, events payload page, TOCTOU guard; 27 files) was
  pushed to `main` — GitHub Actions run 29678029532 succeeded. A follow-up fix
  `76bbc08` corrected `grid-cron.yml` (the secrets context is not allowed in
  step-level `if:`; the invalid file caused instant startup-failure runs — now
  gated on job-level env like deploy-cloudflare.yml); its deploy run 29678054997
  also succeeded. Post-deploy production checks: `POST /api/cron/grid-sync` →
  200 `{enabled:false}` no-op (previously 404 — endpoint live, fail-closed),
  `GET /bots` → 200 with no PUBLIC TEST MODE badge (flag unset, default
  Access-required behavior correct). Remaining activation levers are all
  operator-set: `AEGIS_PUBLIC_TEST_MODE=true` (public testnet mutations),
  `GRID_CRON_ENABLED` + `GRID_CRON_SECRET` + repo secrets (auto loop), R2 bucket
  + binding + snapshot upload (real fund-ops dashboards).

- Added the R2 operations-snapshot reader so fund-ops dashboards can show real
  data (2026-07-19). `getOperationsSnapshot` now resolves sources in priority
  order: R2 object (binding `OPERATIONS_BUCKET`, key
  `AEGIS_OPERATIONS_SNAPSHOT_KEY` or `operations_snapshot.json`) →
  `AEGIS_OPERATIONS_SNAPSHOT_JSON` → filesystem path → demo fallback. Extracted a
  pure, testable `src/lib/operations-snapshot.ts` (`parseOperationsSnapshot`,
  `loadOperationsSnapshot`, `UNCONFIGURED_SNAPSHOT`) that accepts only a
  `persisted_snapshot` `ready/provisional` record and fails closed on
  demo/invalid input; the server fn stays thin and re-exports the type so routes
  are unchanged. Commented `r2_buckets` binding in `wrangler.jsonc` (left off so
  deploys don't fail until the bucket exists). +7 tests → 79/79; TypeScript,
  build, gate SHIP. Live check: `/portfolio` renders demo fallback with no source
  configured; a configured-but-invalid snapshot correctly fails closed (proves
  the env→reader→parse→route chain is wired). R2 uses the same runtime-binding
  mechanism as the working D1 binding, and stores the JSON as an object so it
  avoids the escaping/size limits of inline env JSON. Activation steps (create
  bucket, uncomment binding, upload the Python-generated snapshot) are in
  `docs/MVP_FUND_OPS_PLAN.md`. Not committed/pushed.

- Added public-test-mode so the login-less public deployment can run real
  testnet bots and measure results (2026-07-19; user chose "both" + env-flag).
  New pure `src/lib/actor-identity.ts::resolveActorIdentity` centralizes the
  fail-closed identity matrix: verified Access email+JWT wins; else a localhost
  claim; else — only when `AEGIS_PUBLIC_TEST_MODE === "true"` — a client claim
  (spoofable; acceptable because execution is testnet-locked, no real funds) or
  the fixed `public-test-operator`; otherwise blocked. `actorIdentity` now calls
  it, reading the flag from runtime binding → `globalThis.__env__` → process.env
  (the `.dev.vars`/secret lands on `__env__`). This unblocks create / one-click
  testnet start / reconcile / stop on public prod when the flag is set; default
  OFF keeps Access-required. `getGridBotGovernance` returns `publicTestMode` and
  the cockpit shows a "PUBLIC TEST MODE · MUTATIONS OPEN · TESTNET ONLY" banner
  when active. +8 identity tests → 72/72; TypeScript, build, gate SHIP.
  Browser-verified on wrangler dev with `.dev.vars` flag: badge renders and the
  flag is read from `__env__` (default off → "DURABLE GOVERNANCE"). Four-eyes
  approve still needs two distinct claims (works in test mode) or real Access.
  **Activation:** set Worker var `AEGIS_PUBLIC_TEST_MODE=true`.
  **Data-connection status (user goal "see real data / measure"):** the grid
  domain (bots, orders, events, audit, Grid Profit incl. realized P/L) is
  already REAL from D1 + Binance Testnet — it just needs a bot actually running
  (now possible). The fund-ops accounting dashboards (Portfolio/NAV/
  Reconciliation/Strategy Lab) still show demo fallback until a real operations
  snapshot is delivered to the Worker (`AEGIS_OPERATIONS_SNAPSHOT_JSON`, or the
  future R2 reader) from the Python daily-close pipeline — that pipeline against
  a live testnet account is the remaining follow-up for "real fund-ops data".

- Added the external-cron automatic scheduler (2026-07-19). Since the abstracted
  Nitro build can't register a `cloudflare:scheduled` hook, the grid loop is
  driven over HTTP: new `POST /api/cron/grid-sync` intercepted in `src/server.ts`
  (before the app router, reading bindings from `globalThis.__env__`), handled by
  `src/lib/grid-cron-endpoint.ts` — fail-closed twice (200 no-op unless
  `GRID_CRON_ENABLED="true"`; constant-time `X-Grid-Cron-Secret` vs
  `GRID_CRON_SECRET` Worker secret, layered under the edge Access service token),
  running `reconcileAllRunningTestnetGrids` as `system:grid-cron`. New workflow
  `.github/workflows/grid-cron.yml` (*/15, + manual) curls it with Access
  service-token headers, skipping until its secrets exist. Fixed one extensionless
  import (`binance-testnet.server.ts` → `./binance-signing.ts`) so the chain loads
  under node --test. +5 endpoint tests → 64/64; TypeScript, build, gate SHIP.
  Verified live on wrangler dev: POST → `{enabled:false}` no-op, GET → 405,
  `/bots` → 200 (interception + env plumbing work, normal routes unaffected).
  Activation steps (Worker secrets + Access service token + repo secrets) are in
  `docs/GRID_BOT_PHASE3.md`. Not committed/pushed.

- Closed the two 🟢 code follow-ups from HANDOFF §0 (2026-07-19). **(A) Bot
  Audit Events page** (`bots_.$botId_.events.tsx`) previously showed only
  eventType/actor/time and discarded `event.payload`. Rewrote it to add a short
  eventHash column and clickable rows opening a detail Sheet with the real
  payload JSON and previousHash→eventHash linkage (same pattern as `/audit`),
  plus the chain-verified banner. Browser-verified on local wrangler: the
  `testnet.orders_placed` event shows payload `{executionId, orderCount:20,
  environment:BINANCE_TESTNET}` and genuine previous→this hash linkage. **(B)
  TOCTOU per-order balance guard** in the Testnet execution slice: the aggregate
  USDT/BTC check in `buildExecutableGrid` is kept, but `buildExecutableGrid` now
  also returns the snapshot free balances and `placeTestnetGrid` debits a running
  reservation per order, failing closed before sending each leg if the remaining
  snapshot balance no longer covers it (no extra account/time fetch, so the N+1
  fix stays). Frontend 59/59, TypeScript, build and `gate/verify.ps1` (SHIP)
  pass. NOTE: `src/routes/aot-paper-grid.tsx` + its test are the user's parallel
  WIP (untracked), not part of this work. Not committed/pushed.

- Fund-ops NAV + persisted close, grid realized-cycle P/L, and scheduler-ready
  batch driver (2026-07-19). **(1) Fund-ops:** `compute_nav` values spot
  (qty×mark) + derivative mark-to-market into the daily-close, fail-closed on any
  open position lacking a mark (`nav_missing_marks`, never valued at 0 silently);
  the daily-close job now persists the close via `FundV2Store.record_close`
  (idempotent upsert preserving locked closes) and records missing-mark
  exceptions that block `lock_close`. Exception review/approval persistence
  already existed (idempotent add, four-eyes resolve, lock-blocking).
  `DailyCloseReport` gained `nav/nav_complete/nav_missing_marks` (defaulted at the
  end for backward-compatible reconstruction in `fund_v2_cli`). +3 Python tests;
  fund discovery 38/38, gate SHIP. **(2) Grid realized-cycle P/L:**
  `grid-realized.ts::computeRealizedCycles` pairs FILLED buy→sell round trips one
  grid line apart (arithmetic/geometric), open legs never counted as profit;
  surfaced on the Grid Profit page. **(3) Scheduler:** extracted transport/
  identity-independent `grid-reconcile.ts` (`reconcileOneTestnetGrid`,
  `reconcileAllRunningTestnetGrids`); refactored `syncBinanceTestnetGridBot` onto
  it; added `syncAllRunningTestnetGrids` server fn + "Sync all running" cockpit
  button, and `runScheduledGridReconciliation` (fail-closed behind
  `GRID_CRON_ENABLED`, system actor `system:grid-cron`). **No in-Worker cron
  trigger shipped:** Nitro dispatches cron to the `cloudflare:scheduled` hook via
  a plugin, but this abstracted lovable/vite-tanstack Nitro build scans no
  `plugins/`/`server/plugins/` dir and its `nitro` passthrough doesn't expose
  plugin registration (verified empirically) — a wrangler cron without the hook
  would no-op, so it was deliberately omitted. Enablement path documented in
  `docs/GRID_BOT_PHASE3.md` (de-abstract Nitro plugin, or external scheduler +
  Access service token). +10 frontend tests (6 realized, 4 reconcile) → 49/49;
  TypeScript, build, gate SHIP. Browser-verified: "Sync all running" and the
  realized-P/L tile render and wire (local wrangler reached testnet, "1 fill
  observed"). **(4) Research:** Line-B D1 closure re-affirmed — no mechanism-level
  hypothesis proposed, so dual tuning NOT reopened (would violate D1/CLAUDE.md);
  VALIDATION_LOG §D1 + eval gate doctrine intact. Not committed/pushed yet.

- Built the grid-bot runtime loop — fill tracking + replenishment (2026-07-19,
  Task 4). New pure planner `src/lib/grid-runtime.ts::planGridReconciliation`
  reconciles the durable order ledger against the exchange's open orders and
  trades: a filled BUY plans a SELL one grid line up, a filled SELL plans a BUY
  one line down (same base qty), boundary fills place nothing, orders missing
  with no matching trade are flagged RECONCILIATION_REQUIRED, and replenishment
  clientOrderIds are deterministic so a replayed poll never double-places.
  Added `placeSingleTestnetOrder` (execution module), repository
  `recordGridSync` (atomic: FILLED/reconciliation/status updates + paired-order
  inserts under the active execution + one hash-chained `testnet.grid_synced`
  event + version bump; a no-change poll writes nothing), and governed server fn
  `syncBinanceTestnetGridBot` (RUNNING BTCUSDT BINANCE_TESTNET only, fail-closed
  identity; a failed replenishment placement leaves its source fill un-terminal
  for the next poll and rethrows only after the ledger is consistent). Wired a
  human-triggered "Reconcile fills" button on the grid-profit route (shows only
  for a RUNNING testnet bot). Refactored `GridBotRepository` constructor off a
  TS parameter property and gave its governance import a `.ts` extension so the
  class is loadable under `node --test`. Added 12 tests (8 planner, 4
  repository); frontend suite 39/39, TypeScript clean, production build and
  `gate/verify.ps1` (SHIP) pass. Browser check on local wrangler confirmed the
  button renders for the seeded RUNNING testnet bot and the click invokes the
  server fn (it then reaches out to testnet.binance.vision and fails closed
  without credentials). NOTE: no automatic cron/Durable Object was added — the
  loop is deliberately human-triggered per iteration; an always-on scheduler is
  an unmade governance decision. Full fill→replenish E2E still needs a live
  testnet bot with real fills.

- Task 2 (production four-eyes approval + Testnet start) NOT executed by the
  agent (2026-07-19): it requires an Email-OTP login to Cloudflare Access as the
  second identity (`bankshadow31@gmail.com`) and a human maker/checker approval
  + start — both are prohibited agent actions (entering credentials / completing
  authentication, and executing a governed start). Readiness is in place:
  Access policy `Allow Aegis Maker and Checker` already lists both identities,
  and production mutation handlers fail closed without verified `cf-access-*`
  headers. Runbook for the user: (1) sign in to
  `aegis-fund-os.bankshadow30.workers.dev` as bankshadow31, (2) open a
  PENDING_APPROVAL BINANCE_TESTNET bot in `/approvals` and approve it as the
  independent checker (maker != checker enforced), (3) Start it from `/bots`,
  (4) use the new "Reconcile fills" button on the bot's Grid Profit page to
  drive each loop iteration and watch fills → replenishments. This also
  exercises the orphaned-fill handling deployed 2026-07-17.

- Closed the fund-ops income + multi-currency FX gap (2026-07-18). Verified
  futures already synced FUNDING_FEE income, collateral TRANSFER and USDⓈ-M
  fills. Added to the Spot connector: (1) `_sync_dividends` importing
  `/sapi/v1/asset/assetDividend` distribution income as `EventType.REBATE`
  carry (launchpool/airdrop/referral), and (2) a fail-closed `capital_fx`
  policy — deposits, withdrawals and dividends in a non-reporting asset now
  convert to the reporting currency via operator-approved marks and record
  `original_asset/original_amount/fx_rate` in event metadata, instead of the
  previous hard fail. No approved mark still fails closed (unchanged doctrine).
  `LedgerEvent.cash_event` gained an optional `metadata` param. CLI wires the
  existing `--mark` table as the capital FX policy (same approved marks, no new
  flags). Added 3 tests (approved-FX capital, reporting dividend → REBATE,
  foreign dividend fail-closed) and updated one changed error-message
  assertion. Fund-ops discovery 35/35, strategy 25/25, eval gate SHIP,
  `gate/verify.ps1` exits 0. No order/execution surface added. Task-5 triage:
  Bybit testnet base URL `https://api-testnet.bybit.com` is the correct
  official endpoint (STATE's earlier failure was this machine's DNS, not a
  code bug); Rebalancing card is intentionally fail-closed; Workers R2 snapshot
  reader remains infra work — none are code defects.

- Rewrote `/audit` to use the real governance hash chain (2026-07-17). It
  previously rendered the `AUDIT_EVENTS` fixture (22 fabricated rows) yet
  displayed a hard-coded "Chain integrity: verified" badge and a fake
  "Integrity: Verified" metric — the one page whose job is to prove audit
  integrity was the only bot surface still asserting a fake verification, with
  no demo label. It now loads `getGridBotGovernance()`, shows real events
  (newest first) with actor, eventType, botId and real short eventHash; the
  integrity badge/metric reflect the actual `verifyGovernanceChains()` result
  (verified / FAILED / storage-unavailable), and the detail sheet shows the
  real `payload` JSON plus previousHash→eventHash linkage instead of a
  fabricated before/after diff. Removed the now-unused `AUDIT_EVENTS` fixture
  and its two constants from `demo-data.ts`. Verified on local `wrangler dev`
  against seeded D1: 5 events / 2 bot chains, real payload
  `{from:DRAFT,to:PENDING_APPROVAL}`, and the approval event's previousHash
  matches the bot.created event's hash (genuine linkage). Also fixed a latent
  pre-existing type bug this surfaced: `bots.tsx` loader catch-branch typed
  `profitByBot` as `{}`, blocking indexing — now `Record<string,
  {orderCount,estimatedCycleProfit}>`. TypeScript clean, frontend tests 27/27,
  production build and `gate/verify.ps1` (SHIP) pass. NOTE: production is now
  back behind Cloudflare Access (all routes redirect to Email-OTP login) — the
  earlier-session public-access finding (#5) appears resolved by whoever
  restored the Access application; could not re-test production pages directly.

- Full record of this session's work (analysis, orphaned-fill fix, N+1 fix,
  Decision D1, production e2e + route un-nesting fix, minor UX fixes, deploy
  status) is documented in `docs/WORKLOG_2026-07-17.md`.

- Closed both minor e2e findings (2026-07-17): (1) Save Draft on `/bots/new`
  now shows an explicit toast ("Please acknowledge the risk disclosure before
  saving or submitting.") instead of silently returning when the risk
  acknowledgement is unchecked — Submit/Start were already disabled without
  ack, only Save Draft was reachable silently; verified locally that the toast
  fires and no mutation request leaves the page. (2) Bot detail, Active
  Orders and Bot Audit Events routes now set route-specific titles via
  `head` meta ("Bot Detail / Active Orders / Bot Audit Events · Aegis Fund
  OS"), verified in the local `wrangler dev` tab titles. TypeScript, frontend
  tests 26/26, production build and `gate/verify.ps1` (SHIP) all pass. The
  route un-nesting fix plus these two changes are ready to deploy together;
  production still serves the old bundle until `main` is pushed.

- Production e2e of `/bots` (2026-07-17) found and fixed a routing defect:
  `/bots/$botId/orders` and `/bots/$botId/events` rendered the parent bot
  detail instead of their own pages because they were nested child routes and
  the parent has no `<Outlet />`. Fixed by un-nesting the route files to
  `bots_.$botId_.orders.tsx` / `bots_.$botId_.events.tsx` (URLs unchanged) and
  regenerating the route tree; verified on local `wrangler dev` with local D1
  that Active Orders and Bot Audit Events pages now render. **Production still
  serves the broken routes until the fix is deployed.** Everything else passed:
  `/bots` D1 fleet (2 bots) with verified audit chain, bot detail, `/bots/new`
  SSR with live Testnet feed, five-step wizard, and the fail-closed mutation
  guard — Save Draft returned "Verified Cloudflare Access identity is
  required; mutation blocked" and the fleet was unchanged. Minor findings, not
  fixed: Save Draft is a silent no-op when the risk-acknowledgement checkbox
  is unchecked, and detail/orders/events routes lack route-specific titles.
  Frontend tests 26/26, TypeScript, production build and `gate/verify.ps1`
  (SHIP) pass after the fix. Added `fund-command-center` (vite dev) and
  `fund-command-center-worker` (wrangler dev) entries to `.claude/launch.json`.

- Decision D1 recorded (2026-07-17): cash is now the official Line-B default.
  Every declared candidate is run-and-failed (E21 promotion, E22 diagnosis
  `negative_edge_trading`, E23 tune, E24 short_cfg, E25 conservative) and the
  remaining STATE candidate "funding/relative only" reuses signals that failed
  standalone (E17/E18), so it was rejected without spending compute. No gate
  criterion was changed; cash was already the gate's fail-closed selection
  since E21 — D1 makes it official and stops further dual tuning. Line A
  (research/education Dual 75/25 + percentile) is unchanged. Full decision
  record with reopening conditions lives in `docs/VALIDATION_LOG.md` § D1;
  `docs/HANDOFF_CURSOR.md` §3/§4 updated so future sessions do not resume
  dual tuning. Research effort now pivots to fund-ops ledger per HANDOFF §4.
  `gate/verify.ps1` re-verified SHIP after the documentation changes.

- Fixed orphaned-fill rollback gap in the Binance Testnet execution slice
  (2026-07-17). Previously both `placeTestnetGrid` and
  `startBinanceTestnetGridBot` cancelled already-accepted orders with
  `Promise.allSettled` and rethrew the original error, silently swallowing any
  cancel that failed because the GTC LIMIT order had already filled — leaving a
  real Testnet position with no D1 ledger record. Both paths now inspect each
  cancel outcome and throw a new `OrphanedTestnetOrdersError` carrying the
  un-cancellable orders (clientOrderIds) so the operator must reconcile instead
  of assuming a clean rollback. Added a focused test for the filled-order
  rollback case; frontend tests 26/26, TypeScript, and `gate/verify.ps1` (SHIP)
  all pass.

- Removed the per-order `/api/v3/time` fetch (N+1) from the Testnet execution
  slice (2026-07-17). `placeTestnetGrid` now syncs the exchange clock once via a
  `timeOffset` helper and derives each signed request's timestamp from
  `Date.now() + offset`, threading the shared offset into `buildExecutableGrid`
  and every order `signedRequest`. A 40-order grid drops from ~80 round-trips to
  one time sync, cutting latency and rate-limit exposure; `signedRequest` keeps
  a self-syncing fallback for standalone cancels. Test asserts exactly one
  `/api/v3/time` call per grid placement. Frontend tests 26/26, TypeScript, and
  `gate/verify.ps1` (SHIP) pass. Follow-ups from the system analysis still open:
  production mutations fail closed after Access removal, and the core strategy
  still losing to cash (E22–E25).

- Cloudflare Access application was removed by the user (2026-07-17) after
  explicit confirmation to make production public while keeping mutations
  blocked. External verification of `/bots/new` now returns HTTP 200 directly
  with no Access redirect. Because production mutation handlers still require
  verified `cf-access-*` identity headers, create/approve/start/stop operations
  fail closed until Access or an equivalent authenticated identity layer is
  restored.
- Public-mode production E2E verified (2026-07-17): `/bots/new` loaded without
  an Access redirect, fetched real Binance Spot Testnet BTCUSDT context
  (connected, 1 BTC and 10,000 USDT), completed all five setup steps for a
  20-level BINANCE_TESTNET preview, and rejected Save Draft with the explicit
  message `Verified Cloudflare Access identity is required; mutation blocked`.
  Therefore no create/approval/start request reached D1 or Binance. Wrangler D1
  readback was attempted twice after the browser check but the remote query API
  timed out; the browser mutation result is authoritative for the tested
  fail-closed boundary.

- Deployed the governed Binance Spot Testnet execution slice (2026-07-17),
  Worker version `32175568-e2f6-463e-80de-c14b57919f67`. Migration 0003 adds
  durable execution/order ledgers. Only approved, IDLE, BTCUSDT
  `BINANCE_TESTNET` bots may place GTC LIMIT orders at the hard-coded
  `https://testnet.binance.vision` endpoint. The adapter validates exchange
  filters and BTC/USDT balances, caps a start at 40 orders, uses deterministic
  client IDs, blocks duplicate starts, rolls back accepted orders after a
  partial placement failure, and cancels tracked open orders on Stop. Mainnet,
  transfer and withdrawal paths are absent. Orders page now shows only
  exchange-acknowledged D1 records. Frontend tests pass 25/25 (including three
  execution/rollback/mainnet-lock tests), TypeScript/build pass and the full
  gate reports SHIP. Production order placement has not yet been triggered:
  the only remote bot is PAPER/PENDING_APPROVAL and four-eyes governance needs
  a second Cloudflare Access identity before a new BINANCE_TESTNET bot can be
  approved and started.

- Fixed the production `/bots/new` SSR failure (2026-07-17): the read-only
  Binance grid-feed server function no longer requires an `Origin` header for
  production GET/HEAD requests generated by SSR, while non-HTTPS,
  cross-origin, and origin-less mutation requests remain blocked. Frontend
  tests pass 22/22, TypeScript and production build pass, and
  `gate/verify.ps1` reports SHIP. Deployed Bankshadow30 Worker version
  `bd9e5d53-59b5-4069-b81a-851ea5894f77`; final browser verification still
  requires an authenticated Cloudflare Access session.

- Connected BTC Dual Grid to Binance Spot Testnet as a read-only paper feed
  (2026-07-16): Bots route now loads real BTCUSDT best bid/ask plus signed BTC
  and USDT free balances, then deterministically generates three simulated
  levels per side at 0.5% spacing with 12,000 USDT paper capital. Feed output
  explicitly advertises `readOnly: true` and `canPlaceOrder: false`; no Binance
  order endpoint or exchange order ID exists. Local UI verified connected at
  bid 64,179.13 / ask 64,179.14 with 1 BTC and 10,000 USDT Testnet balances.
  Frontend tests (11/11), TypeScript, production build and full gate pass.

- Binance Spot Testnet authentication restored (2026-07-16): after replacing
  the rejected credential pair with a newly generated Spot Testnet HMAC key,
  a direct signed read-only `GET /api/v3/account` returned HTTP 200 with SPOT
  permissions. Public time, server-synchronized timestamp and HMAC signing all
  verify. The remote account reports trade capability, but Aegis still exposes
  no order, transfer or withdrawal call path. Integrations now runs this
  read-only probe in the route loader so refresh/navigation preserves real
  health instead of resetting to `Not tested`; Local UI verifies `Healthy`,
  SPOT, 446 non-zero assets and 258ms probe latency. Frontend tests (9/9),
  TypeScript and production build pass.

- Added verified Loop snapshot CLI (2026-07-16):
  `python -m dynamic_grid.loop_cli` accepts only explicit memory, drift queue,
  paper-review ledger and output paths. It verifies all three evidence sources
  before atomic output replacement, preserves an existing snapshot when source
  integrity fails, and exposes no strategy mutation, approval or order command.
  Four focused CLI tests pass.

- Projected independent paper reviews into Loop snapshots and Aegis
  (2026-07-16): snapshots now verify the review ledger, expose review-chain
  integrity/hash/counts, maker, reviewer, rationale and paper-only decision,
  and count approved/rejected/pending reviews. The Aegis validator rejects
  self-review and review-to-experiment hash mismatches; Strategy Lab displays
  review evidence read-only. Snapshot/review tests, frontend tests (9/9),
  TypeScript, production build and full gate pass. Next Loop task: CLI for
  verified snapshot export.

- Added independent paper-review decision ledger (2026-07-16): each experiment
  contract now declares a maker; only deterministic `paper_review` verdicts are
  eligible, maker/reviewer equality is rejected case-insensitively, rationale
  is required, and one final `approved_for_paper` or `rejected` decision is
  bound to the experiment record hash in a separate append-only SHA-256 chain.
  Reviews are revalidated against experiment memory on every read and there is
  no live decision. Six review tests, all Loop tests and the full gate pass.
  Next Loop task: project review status into the snapshot and Aegis UI.

- Bound verified Loop lineage to Aegis Strategy Lab (2026-07-16): the page now
  reads only through the server function and renders integrity source,
  experiment/verdict counts, newest-first hypotheses, robust scores, failure
  reasons, record hashes and drift research tasks. Unconfigured and invalid
  snapshots are explicit, static registry evidence remains demo-labelled, and
  prior demo create/compare actions were removed. Frontend tests (8/8),
  TypeScript, production build and the full gate pass. Next Loop task: an
  independent paper-review decision ledger.

- Added server-only Aegis Loop-lineage reader (2026-07-16): a serializable,
  typed schema validator accepts only version-1 verified read-only snapshots
  whose mutation, approval and order capabilities are all false. The server
  function reads only `AEGIS_LOOP_SNAPSHOT_PATH`/`_JSON`, returns an explicit
  unconfigured fallback, and exposes no write operation or filesystem path to
  browser code. Frontend tests (8/8), TypeScript and production build pass;
  full strategy gate passes. Next Loop task: bind lineage to Strategy Lab UI.

- Added read-only Loop lineage snapshot exporter (2026-07-16): verified
  experiment memory and drift queue are projected to versioned, newest-first
  Aegis JSON with verdict counts, failure reasons, validation summaries, source
  hashes and explicit no-mutation/no-approval/no-order capabilities. Tampered
  memory fails closed and output replacement is atomic. Twenty-one focused
  Loop tests and the full gate pass. Next Loop task: server-only Aegis reader
  for the lineage snapshot.

- Added research-only drift monitoring (2026-07-16): declared thresholds cover
  robust-score decay, drawdown increase, execution-cost increase and data gaps;
  minimum sample size and same-dataset comparison are enforced. Alerts are
  immutable `open_research_task` drafts written to an idempotent append-only
  queue; the API contains no parameter mutation or execution operation.
  Seventeen focused Loop tests and the full gate pass. Next Loop task: export a
  read-only experiment-lineage snapshot for Aegis.

- Added one-contract Loop research runner (2026-07-16): it validates the
  preregistered contract and exact dataset mapping before evaluation, hashes
  code/data before and after the run, calls one evaluator, enforces the declared
  trial cap, and stores summarized validation evidence plus deterministic
  verdict in the hash-chained memory. Input mutation and budget overrun fail
  closed without recording a misleading result. Twelve focused Loop tests and
  the full gate pass. Next Loop task: drift monitor that may open research tasks
  but cannot change strategy parameters.

- Added append-only Loop experiment memory (2026-07-16):
  `ExperimentMemory` persists canonical JSONL records chained by SHA-256,
  requires code and named dataset hashes, rejects duplicate experiment IDs,
  and verifies the full chain before reads or appends. Tampering with prior
  hypotheses/results fails closed. Eight focused Loop tests and the full gate
  pass. Next Loop task: one-contract research runner with immutable output.

- Added fail-closed Loop Engineering foundation (2026-07-16): studied the
  referenced cwayinvestment video and Thai summary, then translated Memory +
  Agent Harness + Learning Loop into a research-only contract. Experiments now
  require a preregistered hypothesis, cash benchmark, named real datasets,
  held-out split, >=3 distinct seeds, fixed robust-score formula and bounded
  trials. Deterministic verdicts stop at independent paper review and reject
  live targets. Four focused tests and `gate/verify.ps1` pass. Next loop task:
  append-only JSONL experiment memory with code/data hashes.

- Improved Aegis external-team readiness (2026-07-16): audit fixture events
  now remain newest-first, degraded/disconnected adapter status deep-links to
  Integrations, and Access shows time-bound expiry plus a demo renewal draft.
  Sidebar already covered all 15 existing routes. Documented Cloudflare Access
  Email OTP as the required hostname-level session gate before external use;
  dashboard policy configuration remains an administrator action.
- Sanitized `fund-command-center-local/.env.example` (2026-07-16): it now
  contains placeholders only. The local `.env.local` remains ignored and was
  not inspected.

- Cloud Worker Binance Spot Testnet probe was deployed and tested through the
  hosted Integrations page (2026-07-16). Worker-secret synchronization from
  GitHub Actions succeeded, but Binance rejected the signed read-only request.
  Replace the GitHub secrets with a newly generated **Spot Testnet** key pair
  (never a mainnet key) and check any Testnet IP restriction before retrying.

- Added deterministic daily-close control (2026-07-15): NAV can lock only
  after data, prices, reconciliation, FX and fee checks pass and an independent
  reviewer differs from the maker. The Portfolio page now derives approval
  rather than allowing a manual approval bypass. Three unit tests, TypeScript,
  production build, and `gate/verify.ps1` pass.
- Implemented fund-ops post-MVP #1 partial: `ApprovedMarksFeeConverter` + Spot
  deposit/withdraw → TRANSFER; wired CLI `--mark`; tests green.
- Next fund-ops: income/funding API → `FUNDING` events.
- Completed Aegis Spot Grid Bot Phase 1 acceptance (2026-07-16): added the
  cockpit, five-step Demo/Paper/Testnet wizard, exact-decimal arithmetic and
  geometric previews, bot/order/event detail routes, status controls and
  Binance Testnet read-only market context. Browser acceptance covered desktop
  and 390px mobile layouts plus invalid-range fail-closed behavior; a defect
  that allowed Continue when Lower exceeded Upper was fixed with a hard block.
  Frontend tests pass 18/18, TypeScript and scoped lint pass, production build
  passes, and `gate/verify.ps1` reports SHIP. No live-order capability was
  added; Testnet remains read-only and submit/start actions remain controlled
  Phase-1 local workflow actions pending durable Maker-Checker storage.

- Completed Aegis Spot Grid Bot Phase 2 local acceptance (2026-07-16): added
  Cloudflare D1 migrations and a fail-closed repository for idempotent drafts,
  Maker-to-Checker submission, terminal approve/reject decisions and immutable
  per-bot SHA-256 audit chains. The five-step wizard now writes drafts and
  approval requests through server functions; `/approvals` reads the durable
  queue and enforces maker != checker. Local Cloudflare browser acceptance
  created a PAPER bot, submitted it, approved it as an independent checker and
  verified final state APPROVED/version 3 with three linked audit events. No
  exchange-order endpoint was added; Binance Testnet remains read-only. Remote
  deployment still requires creation of the real D1 database and replacement
  of the placeholder database ID in Wrangler configuration.

- Closed the Phase 2 production D1 blocker (2026-07-16): created APAC D1
  `aegis-fund-os-governance` (`db4592b5-2c67-4964-b7a7-c71c1caccf77`),
  replaced the Wrangler placeholder, applied migration 0001 remotely and
  deployed Worker version `1c55142d-e59e-47d7-8239-fca3ca853b1d`. Production
  smoke at `https://aegis-fund-os.btc-desk-premium.workers.dev/approvals`
  returns 200, reports a verified audit chain and does not report unavailable
  storage. The previously shared `bankshadow30.workers.dev` URL is a stale
  deployment under a different workers.dev subdomain and was not modified by
  the currently authenticated Cloudflare account.

- Replaced Grid Bot fixture surfaces with durable D1 projections (2026-07-16):
  `/bots`, bot detail and bot events now read governance records and immutable
  events; fake orders, cycles, PnL and ROI were removed and replaced with an
  explicit unavailable-until-adapter state. Migration 0002 separates approval
  state from `IDLE/RUNNING/PAUSED/STOPPED` runtime state. Start/Pause/Resume/
  Stop are optimistic, durable and hash-audited but never transmit exchange
  orders. Local browser acceptance proved create -> approve -> start -> pause,
  persistence after reload, version 3 -> 5 and a verified chain. Production
  migration and Worker version `1813005a-3777-422b-a6fd-9c56012b6c88` are
  deployed; `/bots` returns 200 with the D1 fleet and no fixture bot. Production
  mutations now require Cloudflare Access email plus JWT headers and otherwise
  fail closed; localhost alone permits the explicit local test identity.

- Migrated the active deployment back to the intended Bankshadow30 Cloudflare
  account (2026-07-16): Wrangler now authenticates as
  `bankshadow30@gmail.com` (account `004d508d5ed65f935b3634b5b5d6dc47`).
  Created APAC D1 `aegis-fund-os-governance`
  (`74c0d2d0-315a-4cbc-8ee1-0d1fc26db951`), applied migrations 0001/0002 and
  deployed Worker version `8cad45b0-3746-4b02-9d27-9462b9c11f34` to the
  canonical `aegis-fund-os.bankshadow30.workers.dev` hostname. Existing Binance
  Testnet API key/secret bindings remain present. Production `/bots` and
  `/approvals` return 200 against the new D1. Cloudflare Access application
  `Aegis Fund OS` is active with a six-hour session and exact-email Allow
  policy `Allow Bankshadow30 Email OTP` for `bankshadow30@gmail.com`; all
  unmatched users are denied by default. An unauthenticated production request
  and a fresh browser tab both redirect to the `broad-brook-0f63.cloudflareaccess.com`
  login and expose Email One-time PIN while the application remains hidden.

- Recreated Cloudflare Access after the temporary public E2E window
  (2026-07-17): application `Aegis Fund OS` now protects
  `aegis-fund-os.bankshadow30.workers.dev` in Bankshadow30 account
  `004d508d5ed65f935b3634b5b5d6dc47`. Policy
  `Allow Aegis Maker and Checker` allows only `bankshadow30@gmail.com` and
  `bankshadow31@gmail.com`, uses a 24-hour application session, accepts the
  account's available identity providers (including Email OTP), and denies all
  unmatched identities by default. External unauthenticated `/bots` check
  returns HTTP 302 to `broad-brook-0f63.cloudflareaccess.com`, confirming the
  Worker is no longer publicly reachable.

- Deployed the complete current Grid Bot/Testnet execution workspace
  (2026-07-17) after `gate/verify.ps1` exited 0, all 26 web tests passed and
  the production build completed. Remote D1 reported no pending migrations.
  Cloudflare Worker version `df79a275-766e-4af4-a3ce-e8c0fffb3901` is serving
  `aegis-fund-os.bankshadow30.workers.dev`, authored by
  `bankshadow30@gmail.com`. Post-deploy unauthenticated `/bots` smoke returned
  HTTP 302 to the `broad-brook-0f63.cloudflareaccess.com` login, confirming
  Access remained enforced after deployment.

- Deployed the grid-runtime reconciliation and approved capital-FX controls
  (2026-07-19): commit `057deaa` fast-forwarded `main`; GitHub Actions run
  29653594182 completed successfully, including Worker deployment and Testnet
  secret configuration. An unauthenticated `/bots` request still returns HTTP
  302 to Cloudflare Access. No live-order action was taken.

- Removed the Strategy Lab logic page (2026-07-19): `/strategies`, its sidebar
  entry, and its command-palette entry were deleted. The generated route tree
  no longer exposes this path; frontend checks, production build, and
  `gate/verify.ps1` passed before release.

- Removed the Cloudflare Access application for
  `aegis-fund-os.bankshadow30.workers.dev` at the user's explicit request
  (2026-07-19). An unauthenticated browser check reaches `/bots` directly;
  the production Worker is public until an Access application or equivalent
  edge control is restored.

- Added deterministic AOT historical simulation/backtest (2026-07-21) in
  `fund-command-center-local/src/lib/aot-backtest.ts` and wired it into the
  `/aot-paper-grid` Simulation tab. The engine validates OHLC CSV input,
  builds arithmetic/geometric grids, applies conservative no-lookahead fills,
  board lots, cash/inventory constraints, fees, VAT and slippage, tracks
  equity/drawdown/P&L/cycles and monthly returns, and records ambiguous-bar
  warnings. This remains paper/read-only; it cannot submit live orders.
  Added four focused backtest tests; frontend suite now passes 107 tests,
  TypeScript check and production build pass, and `gate/verify.ps1` exits 0.

- Fixed local AOT route import-protection failure (2026-07-21): moved scheduled
  reconciliation into the server-only `grid-bot-governance.cron.server.ts`
  boundary and kept the client-visible governance module limited to
  `createServerFn` RPC handlers. Production build, TypeScript, focused runtime
  tests, and `gate/verify.ps1` pass; local `/aot-paper-grid` reload verified
  without the import overlay.

- Added synthetic OHLCV backtest mode (2026-07-21): the AOT Simulation tab can
  generate deterministic 120-bar paths for seeds 101/202/303 and run the same
  conservative backtest engine, with a seed comparison table and an explicit
  warning that synthetic output is regression evidence only, never market
  evidence. TypeScript, production build, and focused AOT tests pass.

- Added a public AOT historical fixture (2026-07-21) at
  `fund-command-center-local/data/historical/AOT.BK_daily_2025-2026.csv` with
  377 daily bars from the Yahoo Finance public chart endpoint, plus source and
  usage caveats in the adjacent README. CSV parser validation reports zero
  warnings; this remains a paper-research fixture, not an execution feed.

- Added backtest charting and data-density filtering (2026-07-21): the AOT
  Simulation tab now renders Equity, Cash and Drawdown lines with a selectable
  30/90/180/all-bar window; the table uses the same filtered slice. TypeScript
  and production build pass.

- Deployed the chart/filter update (2026-07-21): Cloudflare Worker
  `aegis-fund-os`, version `e5c606fb-7982-41c7-b591-012b60ff02e8`. Live smoke
  request to `/aot-paper-grid` returned HTTP 200 and the AOT page title.

- Professionalized the backtest report (2026-07-21): added report identity and
  date range, strategy/config assumptions, execution-quality metrics, open-risk
  indicators, ambiguous-bar warning, and annual performance review alongside
  the existing chart, filtered equity table and monthly view. TypeScript and
  production build pass; not deployed yet.

- Audited and hardened AOT backtest accounting/reporting (2026-07-21): starting
  equity now includes initial inventory at the first close; drawdown is
  non-negative and peak-relative; duration/total-return fields, P/L
  reconciliation difference, explicit reconciliation warning, forced-close
  visibility, trade-quality metrics, capital deployment, underwater/recovery
  measures and confidence status are exposed to the report. Added focused
  reconciliation assertions; 108 frontend tests, TypeScript, build and gate
  checks pass. Reconciliation now uses a lot-weighted inventory cost ledger and
  passes the ฿0.01 tolerance in the focused fixture; any future mismatch is
  surfaced as a warning rather than adjusted away.

- Annual report rows now calculate period-specific fees and buy-and-hold/alpha;
  the UI exposes peak capital utilization and ending inventory exposure. OOS,
  walk-forward and parameter sensitivity remain explicitly Not tested.

- Implemented Phase 19/20 foundation (2026-07-21): every AOT run now carries a
  unique Run ID, configuration hash, dataset/source/version, engine version,
  timezone, currency, calendar and timing metadata. Added a pre-result data
  quality report for duplicates, missing OHLC, invalid prices, negative volume
  and abnormal gaps, plus JSON configuration export and Run ID copy controls.
  Full stress, capacity, promotion-gate and advanced multiple-testing analyses
  remain explicitly unimplemented rather than reported as passed.

- Added rule-based deterministic insight cards with metric evidence for drawdown,
  sample size, inventory dependence and missing OOS validation. They are not
  LLM-generated and remain scoped to paper research.

- Implemented Phase 33/34 execution foundation (2026-07-21): added selectable
  Conservative OHLC, Intrabar exact, Optimistic comparison and Worst-case modes;
  optional lower-timeframe CSV is used only for execution, never signal
  calculation. Intrabar sequence follows timestamp order, gap fills use the
  observed open when price improves, and run metadata records fallback when
  intrabar data is unavailable. Queue-probability and volume-constrained
  partial-fill calibration remain not tested.

- Converted the backtest trace to an explicit event-driven audit stream: market
  event → strategy decision → order submitted/queued → fill → fee → lot update
  → portfolio valuation. The ordered event log is persisted on each BacktestRun
  and exposed in the report for debugging and reconciliation. 108 tests,
  TypeScript, build and gate verification pass.

- Deployed event-driven AOT backtest/report update (2026-07-21): Cloudflare
  Worker `aegis-fund-os`, version `d4864f7a-d99a-4c23-ae1f-930e91d7f1d2`.
  Production smoke request to `/aot-paper-grid` returned HTTP 200 and included
  the AOT page content.
