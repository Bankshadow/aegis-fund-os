import { Panel } from "@/components/app-shell";

/**
 * Plain-Thai glossary. Student testing showed the lab used 13 unexplained terms
 * (robust, alpha, drawdown, fold, OOS, engaged, C1, C7 …) and gave no sense of
 * scale — a beginner cannot tell whether "robust -17.97" is mildly disappointing
 * or catastrophic. Every entry therefore says what the number MEANS and what
 * counts as good, not just what the word stands for.
 */
/**
 * Live figures from the page the glossary is sitting on. The scale lines used to
 * hardcode the baseline numbers, which then contradicted the screen as soon as a
 * student switched mechanism or cost preset (the exposure-cap view shows -12.17
 * beside a glossary insisting on "about -18"). Passed in where the page has them;
 * omitted, the wording stays qualitative rather than quoting a stale number.
 */
export type GlossaryFigures = {
  robust?: number;
  buyAndHoldRobust?: number;
  drawdown?: number;
  buyAndHoldDrawdown?: number;
  alpha?: number;
};

const fmt = (value: number | undefined, digits = 0, suffix = "") =>
  value === undefined ? null : `${value >= 0 ? "" : "−"}${Math.abs(value).toFixed(digits)}${suffix}`;

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
    scale: "บวก = ชนะการถือเฉย ๆ · ลบ = แพ้ (ตัวเลขคือกี่ % ต่อปีโดยเฉลี่ย)",
  },
  {
    term: "max drawdown (DD)",
    short: "ขาดทุนหนักสุดจากจุดสูงสุดถึงจุดต่ำสุดระหว่างทาง คิดเป็น % — คือความเจ็บที่ต้องทนถือผ่าน",
    scale: "ยิ่งต่ำยิ่งดี · ข้อดีที่ชัดที่สุดของ grid คือกดตัวเลขนี้ให้ต่ำกว่าการถือเฉย ๆ ได้จริง",
  },
  {
    term: "robust",
    short: "คะแนนรวมที่หักโทษความเสี่ยง = ผลตอบแทน − 2 × ขาดทุนหนักสุด (คิดว่าความเจ็บสำคัญเป็น 2 เท่าของกำไร)",
    scale: "ต้องมากกว่า 0 ถึงจะผ่านเกณฑ์ — ดีกว่าการถือเฉย ๆ อย่างเดียวยังไม่พอ",
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

export function WalkForwardGlossary({ figures }: { figures?: GlossaryFigures } = {}) {
  // Only quote a number when this page actually shows it, so the glossary and the
  // table beside it can never disagree.
  const live: Record<string, string | null> = {
    alpha: fmt(figures?.alpha, 2) && `ค่าที่หน้านี้แสดงอยู่: ${fmt(figures?.alpha, 2)}`,
    "max drawdown (DD)":
      fmt(figures?.drawdown, 1, "%") &&
      `ค่าที่หน้านี้แสดงอยู่: grid ${fmt(figures?.drawdown, 1, "%")} · ถือเฉย ๆ ${fmt(figures?.buyAndHoldDrawdown, 1, "%")}`,
    robust:
      fmt(figures?.robust, 2) &&
      `ค่าที่หน้านี้แสดงอยู่: grid ${fmt(figures?.robust, 2)} · ถือเฉย ๆ ${fmt(figures?.buyAndHoldRobust, 2)}`,
  };
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
              {live[entry.term] && <dd className="mt-1 font-mono text-xs text-foreground/70">{live[entry.term]}</dd>}
            </div>
          ))}
        </dl>
      </details>
    </Panel>
  );
}
