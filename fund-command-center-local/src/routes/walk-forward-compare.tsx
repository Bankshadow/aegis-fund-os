import { createFileRoute, Link } from "@tanstack/react-router";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { getWalkForwardComparison } from "@/lib/walk-forward.functions";

export const Route = createFileRoute("/walk-forward-compare")({
  head: () => ({ meta: [{ title: "Mechanism Comparison · Walk-Forward Lab" }] }),
  loader: async () => getWalkForwardComparison(),
  // This page runs THREE full 18-fold walk-forwards (~8s). Without a pending state
  // a student on a phone just sees a dead screen.
  pendingMs: 200,
  pendingComponent: () => (
    <AppShell>
      <div className="p-6 text-sm text-muted-foreground">
        กำลังรัน walk-forward ทั้ง 3 กลไก กลไกละ 18 ช่วงเวลา… ใช้เวลาราว 8 วินาที
      </div>
    </AppShell>
  ),
  component: WalkForwardCompare,
});

const pct = (value: number) => `${value.toFixed(1)}%`;
const signed = (value: number, digits = 2) => `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
const tone = (value: number) => (value >= 0 ? "text-positive" : "text-destructive");

const LABELS = ["Baseline (E26)", "+ Trailing (E28)", "+ Exposure cap (E29)"];

// Each transition's honest teaching point, straight from VALIDATION_LOG §E26-E29.
const NARRATIVE = [
  {
    title: "E26 → E28 : trailing ทำให้ grid กลับมาเทรด แต่แลกด้วย drawdown",
    body: "baseline grid ขายหมดแล้วยืนดูราคาวิ่งหนี — trailing ยกทั้ง grid ตามราคา engaged 83% → 100% และ alpha ดีขึ้นเล็กน้อย แต่การอยู่ในตลาดตลอด trend ทำให้สะสม inventory → drawdown แย่ลง 15.2% → 16.8% และ robust แย่ลง −17.97 → −19.91 สรุป: ซื้อ alpha มาด้วย drawdown",
  },
  {
    title: "E28 → E29 : cap ลด drawdown บน mean แต่ decomposition ล้ม",
    body: "จำกัด long ที่ความจุ grid เดิม → robust ดีขึ้น −19.91 → −12.17, DD 16.8% → 13.5% แต่เทียบ fold ต่อ fold: มีแค่ 6/18 ที่ cap ไม่ทำงาน (ตรง E28) และผลดีส่วนใหญ่มาจาก fold ที่ 'หยุดเทรด' (engaged 100% → 78%, cycles=0) ซึ่งลด drawdown แบบ tautology ไม่ใช่กลไกจริง",
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
    <AppShell>
      <PageHeader
        kicker="EDUCATION · READ-ONLY RESEARCH · NO LIVE ORDER"
        title="เปรียบเทียบกลไก: E26 → E28 → E29"
        subtitle="กลไกทั้งสามบน walk-forward AOT ชุดเดียวกัน — เพิ่มทีละอย่าง เพื่อเห็นว่าอะไรแก้และอะไรไม่แก้"
      />
      <div className="space-y-6 p-6">
        <Panel title="ผลรวมข้างกัน" subtitle="engine เดียวกัน fold เดียวกัน ต่างกันแค่กลไกที่เปิด">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
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

        <Panel title="อ่านผล" subtitle="แต่ละก้าวแก้อะไร (สรุปจาก VALIDATION_LOG §E26–E29)">
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
                ทั้งสามกลไก (และอีก 6 การทดลองก่อนหน้า, E20–E29) ไม่ผ่าน validation gate — geometry, regime filter,
                trailing และ exposure cap ไม่ทำให้ grid มี edge จริงบน AOT รายวัน นี่คือบทเรียนที่จับต้องได้:
                กลไกที่ดู "ปรับปรุงตัวเลขเฉลี่ย" อาจเป็นแค่ selection artifact หรือการหยุดเทรด ไม่ใช่ edge
              </p>
            </div>
          </div>
        </Panel>

        <Panel title="Robust ราย fold ข้ามกลไก" subtitle="fold ที่ cycles=0 คือกลไกทำให้หยุดเทรด (สีแดงที่ช่อง cycles)">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
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
            <Link to="/walk-forward" search={{ variant: "baseline" }}>
              ← กลับไปดูราย fold แบบละเอียด
            </Link>
          </Button>
        </div>

        <p className="text-xs text-muted-foreground">
          Research/education เท่านั้น ไม่ใช่คำแนะนำการลงทุน · เกณฑ์เต็มใน docs/AOT_VALIDATION_CRITERIA.md
        </p>
      </div>
    </AppShell>
  );
}
