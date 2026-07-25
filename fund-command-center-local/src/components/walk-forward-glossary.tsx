import { Panel } from "@/components/app-shell";

/**
 * Plain-Thai glossary. Student testing showed the lab used 13 unexplained terms
 * (robust, alpha, drawdown, fold, OOS, engaged, C1, C7 …) and gave no sense of
 * scale — a beginner cannot tell whether "robust -17.97" is mildly disappointing
 * or catastrophic. Every entry therefore says what the number MEANS and what
 * counts as good, not just what the word stands for.
 */
const TERMS: Array<{ term: string; short: string; scale?: string }> = [
  {
    term: "fold (ช่วงทดสอบ)",
    short:
      "หนึ่งรอบของการทดสอบ: ใช้ข้อมูล 2 ปีแรกตั้งค่ากลยุทธ์ แล้ววัดผลจริงในปีถัดไปที่กลยุทธ์ยังไม่เคยเห็น ทำแบบนี้ 18 รอบเลื่อนไปตามเวลา",
    scale: "ทำหลาย fold เพื่อไม่ให้ผลดีมาจากความบังเอิญของช่วงเวลาเดียว",
  },
  {
    term: "out-of-sample (OOS)",
    short:
      "ช่วงที่กลยุทธ์ยังไม่เคยเห็นตอนตั้งค่า — เป็นการจำลองความจริงว่าเราทำนายอนาคตไม่ได้ ผลในช่วงนี้เท่านั้นที่นับ",
    scale: "ผลใน in-sample (ช่วงที่ใช้ตั้งค่า) ดูดีเสมอ จึงห้ามใช้ตัดสิน",
  },
  {
    term: "return (ผลตอบแทน)",
    short: "กำไร/ขาดทุนรวมของช่วงนั้น คิดเป็น %",
  },
  {
    term: "buy-and-hold (B&H)",
    short: "ซื้อแล้วถือเฉย ๆ ไม่ทำอะไรเลย — เป็นคู่เทียบที่ยุติธรรม เพราะใครก็ทำได้ฟรี",
    scale: "กลยุทธ์ใดชนะไม่ได้ ก็ยังไม่มีเหตุผลให้เหนื่อยเทรด",
  },
  {
    term: "alpha",
    short: "ผลตอบแทนของกลยุทธ์ ลบด้วยผลตอบแทนของการถือเฉย ๆ",
    scale: "บวก = ชนะการถือเฉย ๆ · ลบ = แพ้ · ที่นี่ได้ราว −11 แปลว่าแพ้ประมาณ 11% ต่อปีโดยเฉลี่ย",
  },
  {
    term: "max drawdown (DD)",
    short: "ขาดทุนหนักสุดจากจุดสูงสุดถึงจุดต่ำสุดระหว่างทาง คิดเป็น % — คือความเจ็บที่ต้องทนถือผ่าน",
    scale: "ยิ่งต่ำยิ่งดี · grid ที่นี่ราว 15% ขณะที่ถือเฉย ๆ เจ็บราว 29% (นี่คือข้อดีจริงของ grid)",
  },
  {
    term: "robust",
    short: "คะแนนรวมที่หักโทษความเสี่ยง = ผลตอบแทน − 2 × ขาดทุนหนักสุด (คิดว่าความเจ็บสำคัญเป็น 2 เท่าของกำไร)",
    scale: "ต้องมากกว่า 0 ถึงจะผ่านเกณฑ์ · grid ที่นี่ราว −18 · ถือเฉย ๆ ราว −34 (grid ดีกว่าแต่ยังไม่ถึงเกณฑ์)",
  },
  {
    term: "engaged",
    short: "สัดส่วนช่วงที่กลยุทธ์ได้เทรดจริง (ปิดรอบซื้อ-ขายอย่างน้อย 1 รอบ)",
    scale: "ต่ำ = กลไกทำให้หยุดเทรด ระวัง: ไม่เทรดก็ไม่ขาดทุน ตัวเลขความเสี่ยงจะดูดีขึ้นแบบหลอก ๆ",
  },
  {
    term: "เกณฑ์ C1–C7",
    short:
      "เงื่อนไขที่ประกาศไว้ก่อนรันทดสอบ ห้ามแก้ทีหลัง เช่น C1 = robust ต้อง > 0, C2 = ต้องชนะการถือเฉย ๆ, C7 = ผลต้องไม่ไวต่อการเปลี่ยนค่าพารามิเตอร์เล็กน้อย",
    scale: "ประกาศก่อนรันเพื่อกันการขยับเป้าหลังเห็นผล",
  },
];

export function WalkForwardGlossary() {
  return (
    <Panel title="อ่านก่อน — ศัพท์ที่ใช้ในหน้านี้" subtitle="เปิดดูได้ตลอด ไม่ต้องจำ">
      <details className="group">
        <summary className="cursor-pointer text-sm text-muted-foreground hover:text-foreground">
          กดเพื่อดูคำอธิบายศัพท์ทั้งหมด ({TERMS.length} คำ)
        </summary>
        <dl className="mt-3 grid gap-3 md:grid-cols-2">
          {TERMS.map((entry) => (
            <div className="rounded-md border p-3" key={entry.term}>
              <dt className="text-sm font-semibold">{entry.term}</dt>
              <dd className="mt-1 text-xs text-muted-foreground">{entry.short}</dd>
              {entry.scale && <dd className="mt-1.5 text-xs text-foreground/80">📏 {entry.scale}</dd>}
            </div>
          ))}
        </dl>
      </details>
    </Panel>
  );
}
