import { createFileRoute, Link } from "@tanstack/react-router";
import { PageHeader, Panel } from "@/components/app-shell";
import { EducationShell } from "@/components/education-shell";
import { WalkForwardGlossary } from "@/components/walk-forward-glossary";
import { Button } from "@/components/ui/button";
import { getWalkForwardComparison } from "@/lib/walk-forward.functions";

export const Route = createFileRoute("/walk-forward-compare")({
  head: () => ({ meta: [{ title: "Mechanism Comparison · Walk-Forward Lab" }] }),
  loader: async () => getWalkForwardComparison(),
  pendingMs: 300,
  pendingComponent: () => (
    <EducationShell>
      <div className="p-6 text-sm text-muted-foreground">กำลังโหลดผล…</div>
    </EducationShell>
  ),
  component: WalkForwardCompare,
});

const pct = (value: number) => `${value.toFixed(1)}%`;
const signed = (value: number, digits = 2) => `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
const tone = (value: number) => (value >= 0 ? "text-positive" : "text-destructive");

// Plain-Thai mechanism names; the E-number stays in parentheses for traceability
// back to VALIDATION_LOG without making a student decode it.
const LABELS = [
  "grid ธรรมดา (E26)",
  "+ ยก grid ตามราคา (E28)",
  "+ จำกัดการถือครอง (E29)",
  "+ คืนท่า 50/50 (E30)",
];

// Each transition's honest teaching point, straight from VALIDATION_LOG §E26-E30.
const NARRATIVE = [
  {
    title: "ก้าวที่ 1 — ยก grid ตามราคา: กลับมาเทรดได้ แต่แลกด้วยความเจ็บที่มากขึ้น (E26 → E28)",
    body: "grid ธรรมดาขายหมดแล้วยืนดูราคาวิ่งหนีขึ้นไป พอให้ยก grid ตามราคา มันกลับมาเทรดได้ทุกช่วง (จาก 83% เป็น 100%) และตามหลังการถือเฉย ๆ น้อยลงเล็กน้อย แต่การอยู่ในตลาดตลอดขาขึ้นทำให้สะสมหุ้นไว้มาก พอราคากลับตัวจึงเจ็บหนักขึ้น (ขาดทุนหนักสุด 15.2% → 16.8%) คะแนนรวมจึงแย่ลง −17.97 → −19.91 · บทเรียน: มันไม่ได้ 'ดีขึ้น' แต่ไปแลกความเจ็บมาเพื่อผลตอบแทน",
  },
  {
    title: "ก้าวที่ 2 — จำกัดการถือครอง: ตัวเลขเฉลี่ยดีขึ้น แต่แยกดูราย fold แล้วไม่ใช่ของจริง (E28 → E29)",
    body: "พอห้ามถือหุ้นเกินความจุของ grid เดิม ตัวเลขเฉลี่ยดูดีขึ้นชัด (คะแนนรวม −19.91 → −12.17, ขาดทุนหนักสุด 16.8% → 13.5%) แต่พอแยกดูทีละช่วงกลับไม่ใช่แบบนั้น: ส่วนใหญ่ที่ตัวเลขขยับเป็นเพราะระบบไป 'เลือก' รูปแบบ grid คนละแบบ ไม่ใช่ตัวกลไกเอง และช่วงที่ดูดีขึ้นมากที่สุดคือช่วงที่มัน 'หยุดเทรดไปเลย' (เทรดจริงเหลือ 78% จาก 100%) — ไม่อยู่ในตลาดก็ไม่ขาดทุน ตัวเลขความเสี่ยงเลยสวยขึ้นแบบหลอก ๆ · บทเรียน: ค่าเฉลี่ยที่ดีขึ้นอาจไม่ได้แปลว่ากลไกได้ผล ต้องแยกดูเสมอ",
  },
  {
    title: "ก้าวที่ 3 — คืนท่า 50/50: กลไกถูกทิศ แต่ผลเล็กเกินกว่าจะมี edge (E28 → E30)",
    body: "หน้าจอ Minara บน Hyperliquid ชี้ว่าบัญชีที่ทำเงินแบบมีคุณภาพส่วนใหญ่ไม่ใช่การทายทิศทาง แต่หมุนสองฝั่งแล้วคืน inventory หลังเคลื่อนสั้น ๆ E30 ทำแบบนั้นตอนยกกริด: ขายส่วนที่ถือเกินท่าตั้งต้น แล้ววางกริดใหม่ทั้งสองฝั่ง ผลคือยังเทรดครบทุกช่วง (100% ไม่หยุดแบบ E29) ขาดทุนหนักสุดลดลงนิดเดียว 16.84% → 16.46% คะแนนรวม −19.91 → −19.62 แต่ยังแพ้การถือเฉย ๆ อยู่ดี · 9 ใน 18 ช่วงมีไม้ไม่ถึง 20 ไม้ — กริดหุ้นไทยรายวันไม่มีจังหวะแบบ Type 1 ของ Minara ที่หมุนหลายพันไม้ · บทเรียน: คัดลอก 'สมดุล 50/50' มาได้ แต่คัดลอกสภาพคล่องและจังหวะมาไม่ได้",
  },
];

function WalkForwardCompare() {
  const { variants, folds } = Route.useLoaderData();
  const rows: Array<{ label: string; get: (i: number) => string; toneOf?: (i: number) => string }> = [
    { label: "VERDICT", get: (i) => (variants[i].criteria.passed ? "PASS" : "FAIL"), toneOf: (i) => (variants[i].criteria.passed ? "text-positive" : "text-destructive") },
    { label: "Mean robust", get: (i) => signed(variants[i].summary.meanRobust), toneOf: (i) => tone(variants[i].summary.meanRobust) },
    { label: "Mean alpha vs B&H", get: (i) => signed(variants[i].summary.meanAlpha), toneOf: (i) => tone(variants[i].summary.meanAlpha) },
    { label: "Mean return", get: (i) => pct(variants[i].summary.meanReturn) },
    { label: "Mean max drawdown", get: (i) => pct(variants[i].summary.meanDrawdown) },
    { label: "Engaged (folds ที่เทรด)", get: (i) => pct(variants[i].summary.engagedPct) },
    { label: "ชนะ buy-and-hold", get: (i) => pct(variants[i].summary.beatsBuyHoldPct) },
    { label: "Parameter surface นิ่ง (C7)", get: (i) => pct(variants[i].summary.flatSurfacePct) },
  ];

  return (
    <EducationShell>
      <PageHeader
        kicker="EDUCATION · READ-ONLY RESEARCH · NO LIVE ORDER"
        title="เปรียบเทียบกลไก: เพิ่มทีละอย่าง แล้วดูว่าอะไรดีขึ้นจริง"
        subtitle="กลไกทั้งสี่ทดสอบบนช่วงเวลาชุดเดียวกันทั้งหมด ต่างกันแค่กลไกที่เปิด — จึงเทียบกันได้ตรง ๆ (ตรงกับงานวิจัย E26 → E28 → E29 → E30)"
      />
      <div className="space-y-6 p-6">
        <WalkForwardGlossary />

        <Panel title="ผลรวมข้างกัน" subtitle="engine เดียวกัน ช่วงเวลาเดียวกัน ต่างกันแค่กลไกที่เปิด">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[800px] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-muted-foreground">
                  <th className="p-2">ตัวชี้วัด</th>
                  {LABELS.map((label) => (
                    <th className="p-2" key={label}>
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr className="border-t" key={row.label}>
                    <td className="p-2 text-muted-foreground">{row.label}</td>
                    {variants.map((_, i) => (
                      <td className={`p-2 font-mono ${row.toneOf ? row.toneOf(i) : ""}`} key={i}>
                        {row.get(i)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel title="อ่านผล" subtitle="แต่ละก้าวแก้อะไร (สรุปจาก VALIDATION_LOG §E26–E30)">
          <div className="space-y-4">
            {NARRATIVE.map((item) => (
              <div className="rounded-md border p-4" key={item.title}>
                <div className="font-semibold">{item.title}</div>
                <p className="mt-1 text-sm text-muted-foreground">{item.body}</p>
              </div>
            ))}
            <div className="rounded-md border border-destructive/40 p-4">
              <div className="font-semibold text-destructive">บทสรุป</div>
              <p className="mt-1 text-sm text-muted-foreground">
                ทั้งสี่กลไก (และอีก 6 การทดลองก่อนหน้า, E20–E30) ไม่ผ่าน validation gate — geometry, regime filter,
                trailing, exposure cap และ inventory recycle ไม่ทำให้ grid มี edge จริงบน AOT รายวัน นี่คือบทเรียนที่จับต้องได้:
                กลไกที่ดู "ปรับปรุงตัวเลขเฉลี่ย" อาจเป็นแค่ selection artifact หรือการหยุดเทรด ไม่ใช่ edge และแม้กลไกจะถูกทิศ
                (E30 คืนท่า 50/50 โดยไม่หยุดเทรด) ผลก็ยังเล็กเกินกว่าจะชนะการถือเฉย ๆ บนหุ้นไทยรายวัน
              </p>
            </div>
          </div>
        </Panel>

        <Panel title="Robust ราย fold ข้ามกลไก" subtitle="fold ที่ cycles=0 คือกลไกทำให้หยุดเทรด (สีแดงที่ช่อง cycles)">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[880px] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-muted-foreground">
                  <th className="p-2">Fold</th>
                  <th className="p-2">OOS range</th>
                  {LABELS.map((label) => (
                    <th className="p-2" key={label}>
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {folds.map((fold) => (
                  <tr className="border-t" key={fold.index}>
                    <td className="p-2">{fold.index}</td>
                    <td className="p-2 font-mono text-xs">{fold.oosRange.join(" → ")}</td>
                    {fold.cells.map((cell, i) => (
                      <td className="p-2 font-mono" key={i}>
                        <span className={tone(cell.robust)}>{signed(cell.robust, 1)}</span>{" "}
                        <span className={`text-xs ${cell.engaged ? "text-muted-foreground" : "text-destructive"}`}>
                          cy{cell.cycles}
                        </span>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link to="/walk-forward" search={{ variant: "baseline", cost: "thai" }}>
              ← กลับไปดูราย fold แบบละเอียด
            </Link>
          </Button>
        </div>

        <p className="text-xs text-muted-foreground">
          Research/education เท่านั้น ไม่ใช่คำแนะนำการลงทุน · เกณฑ์เต็มใน docs/AOT_VALIDATION_CRITERIA.md
        </p>
      </div>
    </EducationShell>
  );
}
