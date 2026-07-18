import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AOT_PAPER_MARKET, buildAotPaperGrid } from "@/lib/thai-equity-grid";
import { runAotPaperGridSimulation } from "@/lib/aot-paper-simulation";
import type { GridMode } from "@/lib/grid-bot-domain";
import { ArrowLeft, Calculator, ShieldAlert } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/aot-paper-grid")({
  head: () => ({ meta: [{ title: "AOT Paper Grid · Aegis Fund OS" }] }),
  component: AotPaperGridPage,
});

const thb = (value: string | number) =>
  new Intl.NumberFormat("th-TH", { style: "currency", currency: "THB" }).format(Number(value));

function Field({ label, children, note }: { label: string; children: React.ReactNode; note?: string }) {
  return <label className="grid gap-1.5 text-sm font-medium">{label}{children}{note && <span className="text-xs font-normal text-muted-foreground">{note}</span>}</label>;
}

function AotPaperGridPage() {
  const [referencePrice, setReferencePrice] = useState("40.00");
  const [lowerPrice, setLowerPrice] = useState("36.00");
  const [upperPrice, setUpperPrice] = useState("44.00");
  const [investment, setInvestment] = useState("80000");
  const [gridCount, setGridCount] = useState(8);
  const [mode, setMode] = useState<GridMode>("ARITHMETIC");
  const [costPct, setCostPct] = useState("0.20");
  const [simulation, setSimulation] = useState<ReturnType<typeof runAotPaperGridSimulation> | null>(null);
  const preview = useMemo(() => {
    try {
      return { rows: buildAotPaperGrid({ lowerPrice, upperPrice, referencePrice, investment, gridCount, mode, assumedOneWayCostPct: costPct }), error: "" };
    } catch (error) {
      return { rows: [], error: error instanceof Error ? error.message : "Invalid paper-grid parameters" };
    }
  }, [lowerPrice, upperPrice, referencePrice, investment, gridCount, mode, costPct]);

  return <AppShell>
    <PageHeader
      kicker="SET EQUITY · LOCAL PAPER PREVIEW"
      title="AOT Paper Grid"
      subtitle="Illustrative Thai-equity grid planner. It cannot connect to a broker or submit an order."
      actions={<Button variant="outline" asChild><Link to="/bots"><ArrowLeft className="h-4 w-4" />Bots cockpit</Link></Button>}
    />
    <div className="space-y-5 p-6">
      <div className="rounded-md border border-warning/50 bg-warning/5 p-4 text-sm">
        <div className="flex items-center gap-2 font-semibold"><ShieldAlert className="h-4 w-4" />Paper only — no broker connection</div>
        <p className="mt-1 text-muted-foreground">Prices are entered manually, results are local projections, and no AOT or SET order can be created from this page.</p>
      </div>
      <Panel title="Market constraints" subtitle="Applied to every preview row">
        <div className="grid gap-3 sm:grid-cols-4">
          <Metric label="Symbol" value={AOT_PAPER_MARKET.symbol} />
          <Metric label="Currency" value={AOT_PAPER_MARKET.currency} />
          <Metric label="Board lot" value={`${AOT_PAPER_MARKET.boardLot} shares`} />
          <Metric label="Price tick" value={`฿${AOT_PAPER_MARKET.tickSize}`} />
        </div>
      </Panel>
      <Panel title="Paper parameters" subtitle="Enter an illustrative reference price; this page does not fetch a market quote.">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Field label="Reference price (THB)" note="Manual paper input"><Input inputMode="decimal" value={referencePrice} onChange={(event) => setReferencePrice(event.target.value)} /></Field>
          <Field label="Lower price (THB)"><Input inputMode="decimal" value={lowerPrice} onChange={(event) => setLowerPrice(event.target.value)} /></Field>
          <Field label="Upper price (THB)"><Input inputMode="decimal" value={upperPrice} onChange={(event) => setUpperPrice(event.target.value)} /></Field>
          <Field label="Paper capital (THB)"><Input inputMode="decimal" value={investment} onChange={(event) => setInvestment(event.target.value)} /></Field>
          <Field label="Number of grids"><Input type="number" min={2} max={200} value={gridCount} onChange={(event) => setGridCount(Number(event.target.value))} /></Field>
          <Field label="Grid mode"><select aria-label="AOT grid mode" value={mode} onChange={(event) => setMode(event.target.value as GridMode)} className="h-9 rounded-md border bg-transparent px-3"><option value="ARITHMETIC">Arithmetic</option><option value="GEOMETRIC">Geometric</option></select></Field>
          <Field label="Assumed one-way cost (%)" note="Editable assumption; not a broker quote"><Input inputMode="decimal" value={costPct} onChange={(event) => setCostPct(event.target.value)} /></Field>
          <div className="flex items-end"><Button className="w-full" variant="outline" onClick={() => toast.success("Paper-grid preview recalculated locally. No order sent.")}><Calculator className="h-4 w-4" />Recalculate preview</Button></div>
        </div>
        {preview.error && <p className="mt-4 text-sm text-destructive">{preview.error}</p>}
      </Panel>
      <Panel title="Synthetic opening test" subtitle="Three deterministic synthetic OHLCV paths; 80% validation window and 20% held-out window. This is a system check, not market evidence.">
        <div className="flex flex-wrap items-center gap-3"><Button disabled={Boolean(preview.error)} onClick={() => {
          try {
            setSimulation(runAotPaperGridSimulation({ lowerPrice, upperPrice, referencePrice, investment, gridCount, mode, assumedOneWayCostPct: costPct }));
            toast.success("Three synthetic paths completed locally. No broker or market-data request was made.");
          } catch (error) { toast.error(error instanceof Error ? error.message : "Synthetic test failed closed"); }
        }}>Run 3-seed opening test</Button><span className="text-xs text-muted-foreground">Seeds: 101, 202, 303 · 120 bars/path · synthetic volume only</span></div>
        {simulation && <div className="mt-4 grid gap-3 md:grid-cols-3">{simulation.map((result) => <div className="rounded-md border bg-background/40 p-3" key={result.seed}><div className="font-semibold">Seed {result.seed}</div><div className="mt-2 space-y-1 text-sm text-muted-foreground"><div>Train / hold-out: {result.trainBars} / {result.holdoutBars} bars</div><div>Fill candidates: {result.trainFillCandidates} / {result.holdoutFillCandidates}</div><div>Opening inventory reserve: {result.requiredOpeningInventoryShares} shares</div></div></div>)}</div>}
      </Panel>
      <Panel title="AOT paper ladder" subtitle="All quantities are rounded down to whole 100-share board lots.">
        {preview.rows.length === 0 ? <div className="py-8 text-sm text-muted-foreground">Fix the paper parameters to generate a compliant preview.</div> : <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-sm"><thead className="border-b text-left text-xs uppercase text-muted-foreground"><tr>{["Grid", "Side", "Price", "Shares", "Notional", "Est. one-way cost", "Est. cycle net", "Status"].map((heading) => <th className="p-2" key={heading}>{heading}</th>)}</tr></thead><tbody>{preview.rows.map((row) => <tr className="border-b border-border/50" key={`${row.grid}-${row.side}`}><td className="p-2 font-mono">{row.grid}</td><td className="p-2"><Badge variant="outline" className={row.side === "BUY" ? "border-positive/40 text-positive" : "border-warning/40 text-warning"}>{row.side}</Badge></td><td className="p-2 font-mono">฿{row.price}</td><td className="p-2 font-mono">{row.quantity}</td><td className="p-2">{thb(row.quoteValue)}</td><td className="p-2">{thb(row.estimatedFee)}</td><td className="p-2 text-positive">{thb(row.estimatedNetProfit)}</td><td className="p-2"><Badge variant="secondary">PREVIEW</Badge></td></tr>)}</tbody></table></div>}
      </Panel>
    </div>
  </AppShell>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-md border bg-background/40 p-3"><div className="text-xs text-muted-foreground">{label}</div><div className="mt-1 font-semibold">{value}</div></div>;
}
