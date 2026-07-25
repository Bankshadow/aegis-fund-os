import { createFileRoute, Link } from "@tanstack/react-router";
import { PageHeader, Panel } from "@/components/app-shell";
import { EducationShell } from "@/components/education-shell";
import { WalkForwardGlossary } from "@/components/walk-forward-glossary";
import { Button } from "@/components/ui/button";
import { getWalkForwardView, type WalkForwardVariant } from "@/lib/walk-forward.functions";

// Labels describe the mechanism in plain Thai; the E-number stays in parentheses so
// the research log is still traceable, but a student never has to decode "E26".
const VARIANTS: Array<{ id: WalkForwardVariant; label: string; note: string }> = [
  {
    id: "baseline",
    label: "grid ธรรมดา",
    note: "วาง grid ไว้กับที่ ไม่มีกลไกเสริม — ถ้าราคาวิ่งหนีขึ้นไป grid จะขายหมดแล้วยืนดูเฉย ๆ (งานวิจัย E26)",
  },
  {
    id: "trailing",
    label: "+ ยก grid ตามราคา",
    note: "ถ้าราคาทะลุขึ้นเหนือ grid ให้ยกทั้งชุดขึ้นตาม เพื่อให้กลับมาเทรดได้แทนที่จะยืนดู (งานวิจัย E28)",
  },
  {
    id: "exposure-cap",
    label: "+ จำกัดการถือครอง",
    note: "ยก grid ตามราคาได้ แต่ห้ามถือหุ้นเกินความจุของ grid เดิม เพื่อคุมความเจ็บตอนราคากลับตัว (งานวิจัย E29)",
  },
];

type CostKnobs = { commissionRate?: number; slippageRate?: number; exchangeFeeRate?: number; vatRate?: number };
type WalkForwardSearch = { variant: WalkForwardVariant } & CostKnobs;

// Cost presets in percent (engine divides by 100). Thai retail is the research
// default. "No cost" zeroes EVERY component — a student testing the "it's just the
// fees" theory must get a genuinely fee-free run, not one with VAT still applied.
const COST_PRESETS: Array<{ id: string; label: string } & CostKnobs> = [
  { id: "thai", label: "ต้นทุนจริงไทย (ค่าเริ่มต้น)" },
  { id: "zero", label: "ไม่มีต้นทุนเลย", commissionRate: 0, slippageRate: 0, exchangeFeeRate: 0, vatRate: 0 },
  {
    id: "heavy",
    label: "ต้นทุนสูง (คอม 0.5% + สลิป 0.3%)",
    commissionRate: 0.5,
    slippageRate: 0.3,
  },
];

const num = (value: unknown, max = 2): number | undefined => {
  const n = typeof value === "string" ? Number(value) : typeof value === "number" ? value : NaN;
  return Number.isFinite(n) && n >= 0 && n <= max ? n : undefined;
};

export const Route = createFileRoute("/walk-forward")({
  head: () => ({ meta: [{ title: "Walk-Forward Lab · Aegis Fund OS" }] }),
  validateSearch: (search: Record<string, unknown>): WalkForwardSearch => ({
    variant:
      search.variant === "trailing" || search.variant === "exposure-cap" ? search.variant : "baseline",
    commissionRate: num(search.commissionRate),
    slippageRate: num(search.slippageRate),
    exchangeFeeRate: num(search.exchangeFeeRate),
    vatRate: num(search.vatRate, 20),
  }),
  loaderDeps: ({ search }) => ({ ...search }),
  loader: async ({ deps }) => getWalkForwardView({ data: deps }),
  // Each run is a real 18-fold walk-forward and takes seconds; without this a
  // student on a phone sees a frozen screen and assumes it is broken.
  pendingMs: 200,
  pendingComponent: () => (
    <EducationShell>
      <div className="p-6 text-sm text-muted-foreground">กำลังรัน walk-forward 18 ช่วงเวลาใหม่ทั้งหมด… (ไม่กี่วินาที)</div>
    </EducationShell>
  ),
  component: WalkForwardLab,
});

const pct = (value: number) => `${value.toFixed(1)}%`;
const signed = (value: number, digits = 2) => `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;

function Tile({ label, value, tone, note }: { label: string; value: string; tone?: "pos" | "neg"; note?: string }) {
  const color = tone === "pos" ? "text-positive" : tone === "neg" ? "text-destructive" : "";
  return (
    <div className="rounded-md border p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${color}`}>{value}</div>
      {note && <div className="mt-1 text-xs text-muted-foreground">{note}</div>}
    </div>
  );
}

function WalkForwardLab() {
  const view = Route.useLoaderData();
  const search = Route.useSearch();
  const { variant } = search;
  const { summary, criteria, costs } = view;
  // Carry the current cost knobs onto the variant links so switching mechanism
  // keeps the student's cost scenario.
  const costSearch: CostKnobs = {
    commissionRate: search.commissionRate,
    slippageRate: search.slippageRate,
    exchangeFeeRate: search.exchangeFeeRate,
    vatRate: search.vatRate,
  };
  const KNOBS = ["commissionRate", "slippageRate", "exchangeFeeRate", "vatRate"] as const;
  const activePreset =
    COST_PRESETS.find((preset) => KNOBS.every((knob) => preset[knob] === search[knob]))?.id ?? "custom";

  return (
    <EducationShell>
      <PageHeader
        kicker="EDUCATION · READ-ONLY RESEARCH · NO LIVE ORDER"
        title="Walk-Forward Lab"
        subtitle="ทดสอบกลยุทธ์ grid กับหุ้น AOT รายวัน ปี 2005–2026 แบ่งเป็น 18 ช่วง แต่ละช่วงใช้ข้อมูล 2 ปีแรกตั้งค่า แล้ววัดผลจริงในปีถัดไปที่ยังไม่เคยเห็น (จำลองการเทรดจริงที่ทำนายอนาคตไม่ได้) · engine เดียวกับงานวิจัย E26–E29"
      />
      <div className="space-y-6 p-6">
        <WalkForwardGlossary
          figures={{
            robust: summary.meanRobust,
            buyAndHoldRobust: summary.meanBuyAndHoldRobust,
            drawdown: summary.meanDrawdown,
            buyAndHoldDrawdown: summary.meanBuyAndHoldDrawdown,
            alpha: summary.meanAlpha,
          }}
        />

        <Panel title="เลือกกลไกที่จะทดสอบ" subtitle="แต่ละตัวเพิ่มกลไกทีละอย่างจาก baseline — ดูว่ามันแก้หรือไม่แก้ปัญหา">
          <div className="flex flex-wrap gap-2">
            {VARIANTS.map((item) => (
              <Button key={item.id} variant={item.id === variant ? "default" : "outline"} size="sm" asChild>
                <Link to="/walk-forward" search={{ variant: item.id, ...costSearch }}>
                  {item.label}
                </Link>
              </Button>
            ))}
          </div>
          <p className="mt-3 text-sm text-muted-foreground">{VARIANTS.find((v) => v.id === variant)?.note}</p>
        </Panel>

        <Panel
          title="ต้นทุนธุรกรรม — ปรับแล้วดูผล"
          subtitle="สมมติฐานที่คนชอบคิด: 'grid แพ้เพราะต้นทุน' — ลองกดต้นทุน 0 เทียบดู บนข้อมูลนี้ alpha ยังติดลบ ~11% แปลว่าต้นทุนไม่ใช่สาเหตุ กลไกไม่มี edge ตั้งแต่ต้น"
        >
          <div className="flex flex-wrap gap-2">
            {COST_PRESETS.map((preset) => (
              <Button
                key={preset.id}
                variant={activePreset === preset.id ? "default" : "outline"}
                size="sm"
                asChild
              >
                <Link
                  to="/walk-forward"
                  search={{
                    variant,
                    commissionRate: preset.commissionRate,
                    slippageRate: preset.slippageRate,
                    exchangeFeeRate: preset.exchangeFeeRate,
                    vatRate: preset.vatRate,
                  }}
                >
                  {preset.label}
                </Link>
              </Button>
            ))}
          </div>
          <p className="mt-3 text-sm text-muted-foreground">
            ต้นทุนที่ใช้อยู่: commission {costs.commissionRate}% · slippage {costs.slippageRate}% · exchange fee{" "}
            {costs.exchangeFeeRate}% · VAT {costs.vatRate}%
            {activePreset === "zero" && " — แม้ต้นทุน 0 grid ก็ยังแพ้ buy-and-hold: ต้นทุนไม่ใช่สาเหตุ"}
          </p>
        </Panel>

        <Panel
          title="ผลรวม (out-of-sample)"
          subtitle={
            criteria.passed
              ? "ผ่านเกณฑ์ validation gate"
              : "ไม่ผ่าน gate — นี่คือบทเรียนหลัก: grid ไม่มี edge ที่ผ่านเกณฑ์บนสินทรัพย์นี้"
          }
        >
          <div className={`mb-4 rounded-md border p-3 text-sm ${criteria.passed ? "text-positive" : "text-destructive"}`}>
            VERDICT: {criteria.passed ? "PASS" : "FAIL"} · C1 robust&gt;0 {criteria.C1 ? "✓" : "✗"} · C2 beat B&H{" "}
            {criteria.C2 ? "✓" : "✗"} · C3 DD&lt;B&H {criteria.C3 ? "✓" : "✗"} · C4 engaged {criteria.C4 ? "✓" : "✗"} · C7
            stable {criteria.C7 ? "✓" : "✗"}
          </div>
          <div className="grid gap-3 md:grid-cols-3 lg:grid-cols-4">
            <Tile
              label="Mean robust (return − 2×maxDD)"
              value={signed(summary.meanRobust)}
              tone={summary.meanRobust > 0 ? "pos" : "neg"}
              note={`ต้อง > 0 ถึงผ่าน · ถือเฉย ๆ ได้ ${signed(summary.meanBuyAndHoldRobust)} (grid ดีกว่าแต่ยังไม่ถึงเกณฑ์)`}
            />
            <Tile
              label="Mean alpha vs buy-and-hold"
              value={signed(summary.meanAlpha)}
              tone={summary.meanAlpha > 0 ? "pos" : "neg"}
              note="แพ้ = grid ยังไม่ชนะแค่ถือเฉย ๆ"
            />
            <Tile label="Mean return" value={pct(summary.meanReturn)} note={`buy-and-hold ${pct(summary.meanBuyAndHold)}`} />
            <Tile
              label="Mean max drawdown"
              value={pct(summary.meanDrawdown)}
              tone="pos"
              note={`buy-and-hold ${pct(summary.meanBuyAndHoldDrawdown)} — grid ลด DD ได้จริง`}
            />
            <Tile label="Folds ที่เทรด (engaged)" value={pct(summary.engagedPct)} note="ต่ำ = กลไกทำให้หยุดเทรด" />
            <Tile label="Folds ที่ชนะ B&H" value={pct(summary.beatsBuyHoldPct)} />
            <Tile label="Parameter surface นิ่ง" value={pct(summary.flatSurfacePct)} note="เกณฑ์ C7 ต้อง ≥ 60%" />
            <Tile label="จำนวน folds" value={String(summary.folds)} note="OOS 252 แท่ง/fold" />
          </div>
        </Panel>

        <Panel
          title="ผลราย fold"
          subtitle="แต่ละแถวคือช่วง out-of-sample หนึ่งปี — grid ชนะ fold วิกฤต (ลด DD) แต่แพ้หนักใน fold ขาขึ้นแรง"
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-muted-foreground">
                  {["Fold", "OOS range", "Geometry", "Return", "B&H", "Alpha", "Max DD", "B&H DD", "Robust", "Cycles"].map(
                    (h) => (
                      <th className="p-2" key={h}>
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {view.folds.map((fold) => (
                  <tr className="border-t" key={fold.index}>
                    <td className="p-2">{fold.index}</td>
                    <td className="p-2 font-mono text-xs">{fold.oosRange.join(" → ")}</td>
                    <td className="p-2 text-xs">
                      {fold.gridType} ×{fold.gridCount}
                    </td>
                    <td className="p-2 font-mono">{pct(fold.totalReturn)}</td>
                    <td className="p-2 font-mono text-muted-foreground">{pct(fold.buyAndHoldReturn)}</td>
                    <td className={`p-2 font-mono ${fold.alpha >= 0 ? "text-positive" : "text-destructive"}`}>
                      {signed(fold.alpha)}
                    </td>
                    <td className="p-2 font-mono">{pct(fold.maxDrawdown)}</td>
                    <td className="p-2 font-mono text-muted-foreground">{pct(fold.buyAndHoldDrawdown)}</td>
                    <td className={`p-2 font-mono ${fold.robust >= 0 ? "text-positive" : "text-destructive"}`}>
                      {signed(fold.robust)}
                    </td>
                    <td className={`p-2 font-mono ${fold.engaged ? "" : "text-destructive"}`}>{fold.completedCycles}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <p className="text-xs text-muted-foreground">
          Research/education เท่านั้น ไม่ใช่คำแนะนำการลงทุน ไม่มีการส่งคำสั่งจริง · เกณฑ์เต็มใน docs/AOT_VALIDATION_CRITERIA.md ·
          บันทึกผลใน docs/VALIDATION_LOG.md § E26–E29
        </p>
      </div>
    </EducationShell>
  );
}
