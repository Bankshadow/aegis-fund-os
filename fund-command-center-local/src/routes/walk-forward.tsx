import { createFileRoute, Link } from "@tanstack/react-router";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { getWalkForwardView, type WalkForwardVariant } from "@/lib/walk-forward.functions";

const VARIANTS: Array<{ id: WalkForwardVariant; label: string; note: string }> = [
  { id: "baseline", label: "Baseline grid (E26)", note: "grid ธรรมดา ไม่มีกลไกเสริม" },
  { id: "trailing", label: "+ Trailing (E28)", note: "ยกทั้ง grid ตามราคาเมื่อหลุดขึ้น" },
  { id: "exposure-cap", label: "+ Exposure cap (E29)", note: "จำกัด long ที่ความจุ grid เดิม" },
];

export const Route = createFileRoute("/walk-forward")({
  head: () => ({ meta: [{ title: "Walk-Forward Lab · Aegis Fund OS" }] }),
  validateSearch: (search: Record<string, unknown>): { variant: WalkForwardVariant } => ({
    variant:
      search.variant === "trailing" || search.variant === "exposure-cap"
        ? search.variant
        : "baseline",
  }),
  loaderDeps: ({ search }) => ({ variant: search.variant }),
  loader: async ({ deps }) => getWalkForwardView({ data: { variant: deps.variant } }),
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
  const { variant } = Route.useSearch();
  const { summary, criteria } = view;

  return (
    <AppShell>
      <PageHeader
        kicker="EDUCATION · READ-ONLY RESEARCH · NO LIVE ORDER"
        title="Walk-Forward Lab"
        subtitle="Out-of-sample walk-forward on AOT.BK daily (2005–2026), 18 non-overlapping folds. Geometry is chosen on in-sample bars only; costs are Thai retail. Same engine as the E26–E29 research."
      />
      <div className="space-y-6 p-6">
        <Panel title="เลือกกลไกที่จะทดสอบ" subtitle="แต่ละตัวเพิ่มกลไกทีละอย่างจาก baseline — ดูว่ามันแก้หรือไม่แก้ปัญหา">
          <div className="flex flex-wrap gap-2">
            {VARIANTS.map((item) => (
              <Button key={item.id} variant={item.id === variant ? "default" : "outline"} size="sm" asChild>
                <Link to="/walk-forward" search={{ variant: item.id }}>
                  {item.label}
                </Link>
              </Button>
            ))}
          </div>
          <p className="mt-3 text-sm text-muted-foreground">{VARIANTS.find((v) => v.id === variant)?.note}</p>
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
              note="เกณฑ์ C1 ต้อง > 0"
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
    </AppShell>
  );
}
